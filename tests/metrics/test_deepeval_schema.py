import json

import pytest
from fakes import ScriptedLLM
from pydantic import ValidationError

from chaejeom.llm.base import StructuredOutputError
from chaejeom.metrics import get_metric
from chaejeom.metrics.deepeval.schema import RawStatementVerdicts, RawVerdicts
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="연차휴가는 입사 첫해에 며칠 쓸 수 있나요?",
    contexts=["1개월 개근 시 1일의 유급휴가가 발생한다."],
    answer="한 달 개근마다 하루씩 쓸 수 있습니다.",
)


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _verdicts(*values: str) -> str:
    return _dump({"verdicts": [{"verdict": v, "reason": "이유"} for v in values]})


def test_verdicts_field_is_required():
    with pytest.raises(ValidationError):
        RawVerdicts.model_validate_json("{}")


@pytest.mark.parametrize(("raw", "expected"), [(" Yes.", "yes"), ("idk", "borderline"), ("No, 모순됩니다", "no")])
def test_verdict_is_normalized(raw, expected):
    assert RawVerdicts.model_validate({"verdicts": [{"verdict": raw}]}).verdicts[0].verdict == expected


@pytest.mark.parametrize("raw", ["예", "maybe", None, ""])
def test_verdict_outside_vocabulary_is_rejected(raw):
    with pytest.raises(ValidationError):
        RawVerdicts.model_validate({"verdicts": [{"verdict": raw}]})


def test_statement_verdict_rejects_borderline():
    with pytest.raises(ValidationError):
        RawStatementVerdicts.model_validate({"verdicts": [{"statement": "s", "verdict": "borderline"}]})


@pytest.mark.parametrize("bad", ['{"result": []}', _verdicts("maybe")])
async def test_malformed_verdicts_retry_then_error(bad):
    # Regression: missing or unknown verdicts used to count as "no verdicts" and score 1.0.
    llm = ScriptedLLM([_dump({"truths": ["사실"]}), _dump({"claims": ["주장"]}), bad, bad, bad])
    metric = get_metric("deepeval.faithfulness")(llm=llm, options={"include_reason": False})

    with pytest.raises(StructuredOutputError):
        await metric.ameasure(SAMPLE)
    assert len(llm.calls) == 5


async def test_korean_verdict_is_retried():
    llm = ScriptedLLM([_dump({"statements": ["진술 1", "진술 2"]}), _verdicts("예", "아니오"), _verdicts("yes", "no")])
    metric = get_metric("deepeval.answer_relevancy")(llm=llm, options={"include_reason": False})

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.5
    assert len(llm.calls) == 3
    retry = llm.calls[2]
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    assert "'예'" in retry[-1]["content"]


async def test_contextual_relevancy_missing_verdicts_is_error():
    llm = ScriptedLLM(["{}"] * 3)
    metric = get_metric("deepeval.contextual_relevancy")(llm=llm, options={"include_reason": False})

    with pytest.raises(StructuredOutputError):
        await metric.ameasure(SAMPLE)


async def test_no_statements_keeps_empty_score():
    llm = ScriptedLLM([_dump({"statements": []})])
    metric = get_metric("deepeval.answer_relevancy")(llm=llm, options={"include_reason": False})

    result = await metric.ameasure(SAMPLE)

    assert result.score == 1
    assert len(llm.calls) == 1


async def test_empty_verdict_list_keeps_empty_score():
    llm = ScriptedLLM(['{"verdicts": []}'])
    metric = get_metric("deepeval.contextual_relevancy")(llm=llm, options={"include_reason": False})

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0
