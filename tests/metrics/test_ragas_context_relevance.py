import pytest
from fakes import ScriptedLLM

from chaejeom.metrics import get_metric
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="재택근무는 일주일에 며칠까지 가능한가요?",
    contexts=["재택근무는 주 2일까지 신청할 수 있다.", "사내 식당은 오전 11시 30분부터 운영한다."],
)


def _metric(responses: list[str], **options):
    llm = ScriptedLLM(responses)
    return get_metric("ragas.context_relevance")(llm=llm, options=options), llm


@pytest.mark.parametrize(
    ("ratings", "score", "raw"),
    [((2, 2), 1.0, 2.0), ((2, 1), 0.75, 1.5), ((1, 0), 0.25, 0.5), ((0, 0), 0.0, 0.0)],
)
async def test_score_is_mean_of_halved_ratings(ratings, score, raw):
    metric, llm = _metric([f'{{"rating": {r}}}' for r in ratings])

    result = await metric.ameasure(SAMPLE)

    assert result.score == score
    assert result.raw_score == raw
    assert result.axis == "context_relevance"
    assert [u.verdict for u in result.units] == list(ratings)
    assert [u.type for u in result.units] == ["judge", "judge"]
    assert result.cost.llm_calls == 2
    assert len(llm.calls) == 2


async def test_invalid_rating_is_retried():
    metric, llm = _metric(['{"rating": 3}', '{"rating": 2}', '{"rating": 1}'])

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.75
    assert len(llm.calls) == 3


async def test_one_judge_fails_uses_other():
    metric, _ = _metric(['{"rating": 5}', '{"rating": 7}', '{"rating": 2}'], max_retries=2)

    result = await metric.ameasure(SAMPLE)

    assert result.score == 1.0
    assert result.raw_score == 2.0
    assert [u.verdict for u in result.units] == [None, 2]
    assert "실패" in result.reason


async def test_both_judges_fail_with_errors_sets_error():
    # Like upstream, only the metric's max_retries loop retries; the client's JSON-format retry is disabled.
    metric, llm = _metric(["아님"] * 4, max_retries=2)

    result = await metric.ameasure(SAMPLE)

    assert result.score is None
    assert result.error.startswith("두 판정 프롬프트 모두 오류로 실패했습니다: ")
    assert "ContextRelevanceOutput" in result.error
    assert [u.verdict for u in result.units] == [None, None]
    assert len(llm.calls) == 4


async def test_both_judges_out_of_range_gives_no_score_without_error():
    metric, llm = _metric(['{"rating": 5}'] * 4, max_retries=2)

    result = await metric.ameasure(SAMPLE)

    assert result.score is None
    assert result.error is None
    assert len(llm.calls) == 4


@pytest.mark.parametrize(
    ("query", "contexts"),
    [
        ("   ", ["문맥"]),
        ("질문", ["  "]),
        ("재택근무 규정", ["재택근무 규정"]),
        ("재택근무 규정이 궁금합니다", ["재택근무 규정"]),
    ],
)
async def test_edge_cases_give_zero_without_llm(query, contexts):
    metric, llm = _metric([])

    result = await metric.ameasure(EvalSample(query=query, contexts=contexts))

    assert result.score == 0.0
    assert llm.calls == []


@pytest.mark.parametrize("field", ["query", "contexts"])
async def test_missing_input_raises(field):
    metric, _ = _metric([])
    sample = SAMPLE.model_copy(update={field: [] if field == "contexts" else ""})

    with pytest.raises(ValueError, match=field):
        await metric.ameasure(sample)


async def test_prompts_are_korean_and_judge2_first_person():
    metric, llm = _metric(['{"rating": 2}', '{"rating": 2}'])

    await metric.ameasure(SAMPLE)

    judge1, judge2 = llm.prompt(0), llm.prompt(1)
    assert judge1.startswith("당신은 질문(Question)에 답하기 위한 문맥(Context)")
    assert judge2.startswith("저는 주어진 문맥(Context)")
    for prompt in (judge1, judge2):
        assert "\\u" not in prompt
        assert "예시 3" in prompt
        assert prompt.rstrip().endswith("출력:")
    assert "\\n".join(c.text for c in SAMPLE.contexts) in judge1


def test_default_options():
    metric, _ = _metric([])

    assert metric.options.max_retries == 5
