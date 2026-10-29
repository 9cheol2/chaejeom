import json

import pytest
from fakes import ScriptedLLM

from chaejeom.metrics import get_metric
from chaejeom.metrics.deepeval.prompts.faithfulness import truths_limit_phrase
from chaejeom.metrics.deepeval.qag import (
    YES_NO,
    YES_NO_BORDERLINE,
    normalize_qag_verdict,
    score_qag_verdicts,
)
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="연차휴가는 입사 첫해에 며칠 쓸 수 있나요?",
    contexts=["1개월 개근 시 1일의 유급휴가가 발생한다.", "첫해 유급휴가는 최대 11일이다."],
    answer="한 달 개근마다 하루씩, 최대 11일까지 쓸 수 있고, 남은 휴가는 자동 이월됩니다.",
)

TRUTHS = ["1개월 개근 시 1일의 유급휴가가 발생한다.", "첫해 유급휴가는 최대 11일이다."]
CLAIMS = ["한 달 개근마다 하루의 휴가가 생긴다.", "첫해 휴가는 최대 11일이다.", "남은 휴가는 자동 이월된다.", "휴가는 첫해부터 쓸 수 있다."]


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _verdicts(values: list[str]) -> str:
    return _dump({"verdicts": [{"verdict": v, "reason": f"이유 {i}"} for i, v in enumerate(values)]})


def _metric(responses: list[str], **options):
    llm = ScriptedLLM(responses)
    return get_metric("deepeval.faithfulness")(llm=llm, options=options), llm


def _responses(verdicts: list[str], reason: bool = True) -> list[str]:
    responses = [_dump({"truths": TRUTHS}), _dump({"claims": CLAIMS}), _verdicts(verdicts)]
    if reason:
        responses.append(_dump({"reason": "점수가 0.75인 이유는 이월 규정이 문맥에 없기 때문입니다."}))
    return responses


@pytest.mark.parametrize(
    ("raw", "allowed", "expected"),
    [
        ("yes", YES_NO, "yes"),
        (" No, it's off-topic", YES_NO, "no"),
        ("IDK", YES_NO_BORDERLINE, "borderline"),
        ("idk", YES_NO, None),
        ("borderline", YES_NO, None),
        ("maybe", YES_NO_BORDERLINE, None),
        (None, YES_NO, None),
    ],
)
def test_normalize_qag_verdict(raw, allowed, expected):
    assert normalize_qag_verdict(raw, allowed) == expected


def test_score_qag_verdicts_drops_none_and_uses_empty_score():
    assert score_qag_verdicts(["yes", None, "no"], passing=("yes",)) == 0.5
    assert score_qag_verdicts([], passing=("yes",)) == 1
    assert score_qag_verdicts([], passing=("yes",), empty_score=0) == 0


def test_score_qag_verdicts_all_dropped_raises():
    with pytest.raises(ValueError):
        score_qag_verdicts([None, None], passing=("yes",))


async def test_borderline_passes_by_default():
    metric, llm = _metric(_responses(["yes", "yes", "no", "borderline"]))

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.75
    assert result.reason.startswith("점수가 0.75인 이유는")
    assert result.cost.llm_calls == 4
    assert [u.type for u in result.units] == ["truth", "truth", "claim", "claim", "claim", "claim"]
    assert [u.verdict for u in result.units if u.type == "claim"] == ["yes", "yes", "no", "borderline"]
    assert result.units[0].verdict is None


async def test_penalize_ambiguous_claims():
    metric, llm = _metric(_responses(["yes", "yes", "no", "borderline"]), penalize_ambiguous_claims=True)

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.5
    reason_prompt = llm.prompt(3)
    assert "['이유 2', '(애매함) 이유 3']" in reason_prompt
    assert "0.50" in reason_prompt


async def test_out_of_vocabulary_verdict_is_retried():
    responses = _responses(["yes", "maybe", "no", "Yes."], reason=False) + [_verdicts(["yes", "idk", "no", "Yes."])]
    metric, llm = _metric(responses, include_reason=False)

    result = await metric.ameasure(SAMPLE)

    assert len(llm.calls) == 4
    assert "maybe" in llm.calls[3][-1]["content"]
    assert [u.verdict for u in result.units if u.type == "claim"] == ["yes", "borderline", "no", "yes"]
    assert result.score == 0.75


async def test_no_claims_scores_one_without_verdict_call():
    metric, llm = _metric(
        [_dump({"truths": TRUTHS}), _dump({"claims": []}), _dump({"reason": "모순이 없습니다."})]
    )

    result = await metric.ameasure(SAMPLE)

    assert result.score == 1
    assert len(llm.calls) == 3


async def test_include_reason_false_skips_reason_call():
    metric, llm = _metric(_responses(["yes", "no", "borderline", "no"], reason=False), include_reason=False)

    result = await metric.ameasure(SAMPLE)

    assert len(llm.calls) == 3
    assert result.reason == "판정된 주장 4개 중 yes 1개, borderline 1개, no 2개입니다."


async def test_prompts_korean_and_contexts_joined():
    metric, llm = _metric(_responses(["yes"] * 4), truths_extraction_limit=3)

    await metric.ameasure(SAMPLE)

    truths_prompt, claims_prompt, verdict_prompt = llm.prompt(0), llm.prompt(1), llm.prompt(2)
    assert "\n\n".join(c.text for c in SAMPLE.contexts) in truths_prompt
    assert "문서마다 가장 중요한" in truths_prompt and "3개" in truths_prompt
    assert claims_prompt.rstrip().endswith("JSON:")
    assert f"AI 출력:\n{SAMPLE.answer}" in claims_prompt
    assert str(CLAIMS) in verdict_prompt
    assert "\n\n".join(TRUTHS) in verdict_prompt


def test_truths_limit_phrase():
    assert truths_limit_phrase(None) == "사실에 기반하고 논란의 여지가 없는 사실"
    assert "하나" in truths_limit_phrase(1)
    assert "0개" in truths_limit_phrase(0)


async def test_negative_limit_clamped_to_zero():
    metric, llm = _metric(_responses(["yes"] * 4), truths_extraction_limit=-2)

    await metric.ameasure(SAMPLE)

    assert "0개" in llm.prompt(0)


async def test_missing_input_raises():
    metric, _ = _metric([])
    with pytest.raises(ValueError, match="contexts"):
        await metric.ameasure(SAMPLE.model_copy(update={"contexts": []}))


def test_unknown_option_rejected():
    with pytest.raises(ValueError, match="옵션"):
        _metric([], penalize=True)
