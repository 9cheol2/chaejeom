import json

import pytest
from fakes import ScriptedLLM

from chaejeom.metrics import get_metric
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="연차휴가는 입사 첫해에 며칠 쓸 수 있나요?",
    contexts=[
        "입사 첫해에는 1개월 개근 시 1일의 유급휴가가 발생한다.",
        "첫해에 발생하는 유급휴가는 최대 11일이다.",
    ],
    answer="입사 첫해에는 한 달 개근할 때마다 하루씩, 최대 11일까지 쓸 수 있습니다. 쓰지 않은 휴가는 다음 해로 자동 이월됩니다.",
)

STATEMENTS = [
    "입사 첫해에는 한 달 개근할 때마다 하루의 휴가가 생긴다.",
    "입사 첫해의 휴가는 최대 11일이다.",
    "쓰지 않은 휴가는 다음 해로 자동 이월된다.",
    "휴가는 입사 첫해부터 쓸 수 있다.",
]


def _verdicts(values: list[int]) -> str:
    return json.dumps(
        {
            "statements": [
                {"statement": s, "reason": f"이유 {i}", "verdict": v}
                for i, (s, v) in enumerate(zip(STATEMENTS, values))
            ]
        },
        ensure_ascii=False,
    )


def _metric(responses: list[str]):
    llm = ScriptedLLM(responses)
    return get_metric("ragas.faithfulness")(llm=llm), llm


async def test_score_is_ratio_of_supported_statements():
    metric, _ = _metric([json.dumps({"statements": STATEMENTS}, ensure_ascii=False), _verdicts([1, 1, 0, 1])])

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.75
    assert result.raw_score == 0.75
    assert result.axis == "groundedness"
    assert [u.verdict for u in result.units] == [1, 1, 0, 1]
    assert all(u.type == "statement" for u in result.units)
    assert result.reason == "진술 4개 중 3개가 문맥에서 직접 추론됩니다."
    assert result.cost.llm_calls == 2
    assert result.cost.tokens == 20


async def test_no_statements_gives_no_score():
    metric, llm = _metric(['{"statements": []}'])

    result = await metric.ameasure(SAMPLE)

    assert result.score is None
    assert len(llm.calls) == 1


async def test_empty_verdicts_gives_no_score():
    metric, _ = _metric([json.dumps({"statements": STATEMENTS}, ensure_ascii=False), '{"statements": []}'])

    result = await metric.ameasure(SAMPLE)

    assert result.score is None


@pytest.mark.parametrize("field", ["answer", "query", "contexts"])
async def test_missing_input_raises(field):
    metric, _ = _metric([])
    sample = SAMPLE.model_copy(update={field: [] if field == "contexts" else ""})

    with pytest.raises(ValueError, match=field):
        await metric.ameasure(sample)


async def test_prompts_are_korean_and_contexts_joined():
    metric, llm = _metric([json.dumps({"statements": STATEMENTS}, ensure_ascii=False), _verdicts([1, 1, 1, 1])])

    await metric.ameasure(SAMPLE)

    statement_prompt, verdict_prompt = llm.prompt(0), llm.prompt(1)
    assert statement_prompt.startswith("질문(question)과 답변(answer)이 주어지면")
    assert "예시 1" in statement_prompt
    assert statement_prompt.rstrip().endswith("출력:")
    assert "\\u" not in statement_prompt
    assert "\\n".join(c.text for c in SAMPLE.contexts) in verdict_prompt
