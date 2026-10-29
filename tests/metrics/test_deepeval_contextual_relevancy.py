import json

from fakes import ScriptedLLM

from chaejeom.metrics import get_metric
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="재택근무는 일주일에 며칠까지 가능한가요?",
    contexts=[
        {"id": "hr-12", "text": "재택근무는 주 2일까지 신청할 수 있으며, 팀장 승인이 필요하다.", "rank": 1},
        {"id": "hr-31", "text": "사내 식당은 오전 11시 30분부터 운영한다.", "rank": 2},
    ],
)


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _metric(responses: list[str], **options):
    llm = ScriptedLLM(responses)
    return get_metric("deepeval.contextual_relevancy")(llm=llm, options=options), llm


FIRST = _dump(
    {
        "verdicts": [
            {"statement": "재택근무는 주 2일까지 신청할 수 있다", "verdict": "yes"},
            {"statement": "팀장 승인이 필요하다", "verdict": "yes"},
        ]
    }
)
SECOND = _dump(
    {"verdicts": [{"statement": "사내 식당은 11시 30분부터 운영한다", "verdict": "no", "reason": "'사내 식당' 은 재택근무와 관련이 없습니다."}]}
)


async def test_score_and_context_ids():
    metric, llm = _metric([FIRST, SECOND, _dump({"reason": "점수가 0.67인 이유는 ..."})])

    result = await metric.ameasure(SAMPLE)

    assert result.score == 2 / 3
    assert result.axis == "context_relevance"
    assert [u.context_ids for u in result.units] == [["hr-12"], ["hr-12"], ["hr-31"]]
    assert [u.verdict for u in result.units] == ["yes", "yes", "no"]
    assert result.cost.llm_calls == 3
    reason_prompt = llm.prompt(2)
    assert "[\"'사내 식당' 은 재택근무와 관련이 없습니다.\"]" in reason_prompt
    assert "['재택근무는 주 2일까지 신청할 수 있다', '팀장 승인이 필요하다']" in reason_prompt


async def test_one_call_per_context_with_its_text():
    metric, llm = _metric([FIRST, SECOND], include_reason=False)

    await metric.ameasure(SAMPLE)

    assert len(llm.calls) == 2
    assert f"문맥:\n{SAMPLE.contexts[0].text}" in llm.prompt(0)
    assert f"문맥:\n{SAMPLE.contexts[1].text}" in llm.prompt(1)
    assert f"입력:\n{SAMPLE.query}" in llm.prompt(0)


async def test_no_statements_scores_zero():
    metric, _ = _metric(['{"verdicts": []}', '{"verdicts": []}'], include_reason=False)

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0
    assert result.units == []


async def test_borderline_is_out_of_vocabulary_and_retried():
    # The upstream schema only allows yes/no, so "borderline" is treated as malformed and retried.
    second = _dump({"verdicts": [{"statement": "식당 운영 시간", "verdict": "borderline"}]})
    metric, llm = _metric([FIRST, second, SECOND], include_reason=False)

    result = await metric.ameasure(SAMPLE)

    assert result.score == 2 / 3
    assert [u.verdict for u in result.units] == ["yes", "yes", "no"]
    assert len(llm.calls) == 3
    assert "borderline" in llm.calls[2][-1]["content"]
