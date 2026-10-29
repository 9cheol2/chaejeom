import json

import pytest
from fakes import ScriptedLLM

from chaejeom.cache import ResponseCache
from chaejeom.metrics import get_metric
from chaejeom.metrics.trulens.groundedness import split_sentences
from chaejeom.schema import EvalSample


class RecordingLLM(ScriptedLLM):
    """Also records the system prompt."""

    def __init__(self, responses):
        super().__init__(responses)
        self.systems: list[str | None] = []

    async def _complete(self, messages, system, json_mode):
        self.systems.append(system)
        return await super()._complete(messages, system, json_mode)


def _judgment(score: int, evidence: str = "근거") -> str:
    return json.dumps({"criteria": "진술", "supporting_evidence": evidence, "score": score}, ensure_ascii=False)


SAMPLE = EvalSample(
    query="연차휴가는 입사 첫해에 며칠 쓸 수 있나요?",
    contexts=[
        {"id": "hr-1", "text": "입사 첫해에는 1개월 개근 시 1일의 유급휴가가 발생한다.", "rank": 1},
        {"id": "hr-2", "text": "사내 식당은 오전 11시 30분부터 운영한다.", "rank": 2},
    ],
    answer="안녕하세요. 입사 첫해에는 한 달 개근할 때마다 하루씩 생깁니다. 쓰지 않은 휴가는 다음 해로 자동 이월됩니다.",
)

SENTENCES = [
    "안녕하세요.",
    "입사 첫해에는 한 달 개근할 때마다 하루씩 생깁니다.",
    "쓰지 않은 휴가는 다음 해로 자동 이월됩니다.",
]


def _metric(metric_id, responses, options=None):
    llm = RecordingLLM(responses)
    return get_metric(metric_id)(llm=llm, options=options), llm


def test_kiwi_splits_korean_paragraph():
    assert split_sentences(SAMPLE.answer) == SENTENCES


async def test_groundedness_filters_trivial_and_averages():
    trivial = str(SENTENCES[1:])
    metric, llm = _metric("trulens.groundedness", [trivial, _judgment(3, "1개월 개근 시 1일"), _judgment(1, "NOTHING FOUND")])

    result = await metric.ameasure(SAMPLE)

    assert result.raw_score == 2
    assert result.score == pytest.approx(2 / 3)
    assert [u.text for u in result.units] == SENTENCES[1:]
    assert [u.score for u in result.units] == [3, 1]
    assert result.units[1].reason == "NOTHING FOUND"
    assert all(u.type == "sentence" for u in result.units)
    assert result.cost.llm_calls == 3

    assert llm.prompt(0) == f"전체 진술: {SENTENCES}\n중요한 진술: "
    judge_prompt = llm.prompt(1)
    assert judge_prompt.startswith("근거 자료: " + "\n\n".join(c.text for c in SAMPLE.contexts))
    assert f"진술: {SENTENCES[1]}" in judge_prompt
    assert llm.systems[1].startswith("당신은 정보 겹침 분류기입니다.")


async def test_groundedness_all_trivial_is_zero():
    metric, llm = _metric("trulens.groundedness", ["[]"])

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.0
    assert result.units == []
    assert len(llm.calls) == 1


async def test_groundedness_keeps_all_when_trivial_reply_unreadable():
    metric, _ = _metric("trulens.groundedness", ["모르겠습니다", _judgment(3), _judgment(3), _judgment(0)])

    result = await metric.ameasure(SAMPLE)

    assert len(result.units) == 3
    assert result.raw_score == 2


async def test_groundedness_trivial_reply_in_code_block():
    metric, _ = _metric("trulens.groundedness", [f"```python\n{SENTENCES[2:]}\n```", _judgment(0)])

    result = await metric.ameasure(SAMPLE)

    assert [u.text for u in result.units] == SENTENCES[2:]


async def test_groundedness_llm_splitter_without_trivial_filter():
    metric, llm = _metric(
        "trulens.groundedness",
        ["입사 첫해에는 하루씩 생깁니다.\n1.\n자동 이월됩니다.", _judgment(2), _judgment(0)],
        options={"use_sent_tokenize": False, "filter_trivial_statements": False},
    )

    result = await metric.ameasure(SAMPLE)

    assert llm.prompt(0) == SAMPLE.answer
    assert llm.systems[0].startswith("다음 진술을 개별 문장으로 나누세요")
    assert [u.text for u in result.units] == ["입사 첫해에는 하루씩 생깁니다.", "자동 이월됩니다."]
    assert result.raw_score == 1


async def test_groundedness_skips_unparsable_and_errors_when_none_graded():
    options = {"filter_trivial_statements": False}
    metric, _ = _metric("trulens.groundedness", [_judgment(3), "Supporting Evidence: 점수 없음", _judgment(1)], options)

    partial = await metric.ameasure(SAMPLE)

    assert partial.raw_score == 2
    assert partial.units[1].score is None

    metric, _ = _metric("trulens.groundedness", ["Supporting Evidence: 없음"] * 3, options)
    failed = await metric.ameasure(SAMPLE)

    assert failed.score is None
    assert failed.error


async def test_context_relevance_per_chunk():
    responses = [
        "Criteria: 질의와의 관련성\nSupporting Evidence: 연차 발생 기준을 설명합니다.\nScore: 3",
        "Criteria: 질의와의 관련성\nSupporting Evidence: 식당 운영 시간은 무관합니다.\nScore: 0",
    ]
    metric, llm = _metric("trulens.context_relevance", responses)

    result = await metric.ameasure(SAMPLE)

    assert result.raw_score == 1.5
    assert result.score == 0.5
    assert [u.context_ids for u in result.units] == [["hr-1"], ["hr-2"]]
    assert [u.score for u in result.units] == [3, 0]
    assert all(u.type == "chunk" for u in result.units)
    assert result.units[1].reason.startswith("식당 운영 시간은 무관합니다.")

    prompt = llm.prompt(0)
    assert prompt.startswith(f"사용자 질의: {SAMPLE.query}\n검색 결과: {SAMPLE.contexts[0].text}")
    assert "Supporting Evidence: <" in prompt
    assert llm.systems[0].startswith("당신은 전문 검색 결과 평가자입니다.")


async def test_answer_relevance():
    metric, llm = _metric("trulens.answer_relevance", [_judgment(2, "연차 일수는 답했지만 이월은 틀림")])

    result = await metric.ameasure(SAMPLE)

    assert result.score == pytest.approx(2 / 3)
    assert result.raw_score == 2
    assert result.reason == "연차 일수는 답했지만 이월은 틀림"
    assert result.units == []
    assert llm.prompt(0).startswith(f"프롬프트: {SAMPLE.query}\n응답: {SAMPLE.answer}")
    assert llm.prompt(0).rstrip().endswith("이제 JSON 객체를 생성하세요.")
    assert llm.systems[0].startswith("당신은 관련성 채점자입니다.")


async def test_answer_relevance_unparsable():
    metric, _ = _metric("trulens.answer_relevance", ["Supporting Evidence: 점수 없음"])

    result = await metric.ameasure(SAMPLE)

    assert result.score is None
    assert result.error


async def test_unparsable_reply_is_not_cached(tmp_path):
    cache = ResponseCache(tmp_path)
    metric, llm = _metric("trulens.answer_relevance", ["모르겠습니다", _judgment(2)])
    llm.cache = cache

    first = await metric.ameasure(SAMPLE)
    second = await metric.ameasure(SAMPLE)
    third = await metric.ameasure(SAMPLE)

    assert first.error and first.score is None
    assert second.raw_score == 2 and second.cost.llm_calls == 1
    assert third.raw_score == 2 and third.cost.cache_hits == 1
    assert len(llm.calls) == 2


async def test_unreadable_trivial_reply_is_not_cached(tmp_path):
    metric, llm = _metric("trulens.groundedness", ["모르겠습니다", _judgment(3), _judgment(3), _judgment(3), "[]"])
    llm.cache = ResponseCache(tmp_path)

    await metric.ameasure(SAMPLE)
    again = await metric.ameasure(SAMPLE)

    assert again.score == 0.0
    assert len(llm.calls) == 5


@pytest.mark.parametrize(
    ("metric_id", "requires"),
    [
        ("trulens.groundedness", {"answer", "contexts"}),
        ("trulens.context_relevance", {"query", "contexts"}),
        ("trulens.answer_relevance", {"query", "answer"}),
    ],
)
def test_registration(metric_id, requires):
    metric = get_metric(metric_id)
    assert set(metric.requires) == requires
    assert metric.source.framework == "trulens"
