import json

from fakes import ScriptedLLM

from chaejeom.metrics import get_metric
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(query="재택근무는 일주일에 며칠까지 가능한가요?", answer="주 2일까지 가능합니다. 사내 식당은 11시 30분에 엽니다.")
STATEMENTS = ["재택근무는 주 2일까지 가능하다.", "팀장 승인이 필요하다.", "사내 식당은 11시 30분에 연다."]


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _metric(responses: list[str], **options):
    llm = ScriptedLLM(responses)
    return get_metric("deepeval.answer_relevancy")(llm=llm, options=options), llm


def _verdicts(values: list[str]) -> str:
    return _dump({"verdicts": [{"verdict": v, "reason": f"이유 {i}"} for i, v in enumerate(values)]})


async def test_yes_and_borderline_pass():
    metric, llm = _metric(
        [_dump({"statements": STATEMENTS}), _verdicts(["yes", "borderline", "no"]), _dump({"reason": "점수가 0.67인 이유는 ..."})]
    )

    result = await metric.ameasure(SAMPLE)

    assert result.score == 2 / 3
    assert result.axis == "answer_relevance"
    assert [u.verdict for u in result.units] == ["yes", "borderline", "no"]
    assert all(u.type == "statement" for u in result.units)
    reason_prompt = llm.prompt(2)
    assert "['이유 2']" in reason_prompt
    assert "0.67" in reason_prompt
    assert SAMPLE.query in reason_prompt


async def test_no_statements_scores_one():
    metric, llm = _metric([_dump({"statements": []}), _dump({"reason": "관련 없는 진술이 없습니다."})])

    result = await metric.ameasure(SAMPLE)

    assert result.score == 1
    assert len(llm.calls) == 2


async def test_include_reason_false():
    metric, llm = _metric([_dump({"statements": STATEMENTS}), _verdicts(["yes", "no", "no"])], include_reason=False)

    result = await metric.ameasure(SAMPLE)

    assert len(llm.calls) == 2
    assert result.score == 1 / 3
    assert result.reason == "판정된 진술 3개 중 yes 1개, borderline 0개, no 2개입니다."


async def test_prompts_korean():
    metric, llm = _metric([_dump({"statements": STATEMENTS}), _verdicts(["yes"] * 3)], include_reason=False)

    await metric.ameasure(SAMPLE)

    assert llm.prompt(0).startswith("주어진 텍스트를 나누어")
    assert f"텍스트:\n{SAMPLE.answer}" in llm.prompt(0)
    assert f"입력:\n{SAMPLE.query}" in llm.prompt(1)
    assert str(STATEMENTS) in llm.prompt(1)
