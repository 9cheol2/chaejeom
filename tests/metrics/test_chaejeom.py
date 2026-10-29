import json

import pytest
from fakes import ScriptedLLM

from chaejeom.evaluate import evaluate
from chaejeom.metrics import get_metric
from chaejeom.metrics.chaejeom.scoring import (
    answer_kind,
    answer_relevance_level,
    chunk_verdict,
    context_relevance_level,
    find_quote,
    groundedness_level,
    missing_numbers,
)
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(
    query="연차휴가는 입사 첫해에 며칠 쓸 수 있나요?",
    contexts=[
        {"id": "hr-11", "text": "근로자가 입사 후 1년 미만인 경우 1개월 개근 시 1일의 유급휴가가 발생한다."},
        {"id": "hr-12", "text": "입사 첫해에 발생하는 유급휴가는 최대 11일이다."},
        {"id": "gen-05", "text": "사내 식당은 오전 11시 30분부터 운영한다."},
    ],
    answer="입사 첫해에는 한 달 개근할 때마다 하루씩, 최대 11일까지 쓸 수 있습니다. 쓰지 않은 휴가는 다음 해로 자동 이월됩니다.",
)


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _statement(text, verdict, core=True, quote="", context_id=""):
    return {"statement": text, "core": core, "verdict": verdict, "context_id": context_id, "quote": quote, "reason": "이유입니다."}


def _sentences(*statements_per_sentence):
    return {"sentences": [{"id": f"s{i}", "statements": list(items)} for i, items in enumerate(statements_per_sentence, start=1)]}


def _answer(evasive=False, same_target=True, discusses_asked=True, answers_directly=True, irrelevant_parts=()):
    return _json(
        {
            "question_target": "연차휴가",
            "answer_target": "연차휴가",
            "evasive": evasive,
            "same_target": same_target,
            "discusses_asked": discusses_asked,
            "answers_directly": answers_directly,
            "irrelevant_parts": list(irrelevant_parts),
            "reason": "이유입니다.",
        }
    )


async def _measure(metric_id, response, sample=SAMPLE):
    llm = ScriptedLLM([response])
    result = await get_metric(metric_id)(llm=llm).ameasure(sample)
    return result, llm


@pytest.mark.parametrize(
    ("statements", "level"),
    [
        ([], None),
        ([("supported", True), ("supported", False)], 1.0),
        ([("supported", True), ("unsupported", False)], 0.75),
        ([("supported", True), ("unsupported", True)], 0.5),
        ([("supported", True), ("contradicted", False)], 0.25),
        ([("unsupported", True), ("supported", False)], 0.0),
        ([("contradicted", True)], 0.0),
        # With no statement marked key, every statement counts as key.
        ([("supported", False), ("unsupported", False)], 0.5),
    ],
)
def test_groundedness_levels(statements, level):
    assert groundedness_level(statements)[0] == level


@pytest.mark.parametrize(
    ("verdicts", "level"),
    [
        (["relevant", "relevant"], 1.0),
        (["relevant", "partial"], 1.0),
        (["relevant", "relevant", "irrelevant"], 0.75),
        (["relevant", "partial", "partial", "irrelevant"], 0.75),
        (["relevant", "irrelevant"], 0.5),
        (["relevant"] + ["irrelevant"] * 9, 0.5),
        (["partial"], 0.25),
        (["partial"] * 5 + ["irrelevant"] * 5, 0.25),
        (["irrelevant", "irrelevant"], 0.0),
        ([], 0.0),
    ],
)
def test_context_relevance_levels(verdicts, level):
    assert context_relevance_level(verdicts)[0] == level


@pytest.mark.parametrize(
    ("kind", "extra", "level"),
    [("direct", False, 1.0), ("direct", True, 0.75), ("indirect", False, 0.5), ("other_aspect", False, 0.25), ("off_topic", False, 0.0), ("evasive", False, 0.0)],
)
def test_answer_relevance_levels(kind, extra, level):
    assert answer_relevance_level(kind, extra)[0] == level


@pytest.mark.parametrize(
    ("about_target", "has_answer", "verdict"),
    [(True, True, "relevant"), (False, True, "irrelevant"), (True, False, "partial"), (False, False, "irrelevant")],
)
def test_chunk_verdict(about_target, has_answer, verdict):
    assert chunk_verdict(about_target, has_answer) == verdict


@pytest.mark.parametrize(
    ("flags", "kind"),
    [
        ((True, True, True, True), "evasive"),
        ((False, False, True, True), "off_topic"),
        ((False, True, True, True), "direct"),
        ((False, True, True, False), "indirect"),
        ((False, True, False, False), "other_aspect"),
        ((True, True, True, True, True), "declined"),
    ],
)
def test_answer_kind(flags, kind):
    assert answer_kind(*flags) == kind


def test_find_quote_ignores_spacing_and_prefers_cited_context():
    texts = {"a": "입사 첫해에 발생하는 유급휴가는 최대 11일이다.", "b": "같은 문장 없음"}

    assert find_quote("입사 첫해에 발생하는 유급 휴가는 최대 11일이다.", texts, "b") == "a"
    assert find_quote("최대 12일", texts) is None
    assert find_quote("", texts) is None
    # Quotes below the minimum length are not searched for.
    assert find_quote("11일", texts) is None


def test_find_quote_accepts_edited_endings_and_skipped_middles():
    texts = {
        "law": "계약갱신요구권은 1회에 한하여 행사할 수 있으며, 갱신되는 임대차의 존속기간은 2년으로 본다.",
        "bank": "가입 후 6개월 미만 해지 시 약정 이율의 50%, 6개월 이상 해지 시 약정 이율의 70%를 적용한다.",
    }

    assert find_quote("계약갱신요구권은 1회에 한하여 행사할 수 있다", texts) == "law"
    assert find_quote("가입 후 6개월 미만 해지 시 약정 이율의 50%를 적용한다", texts) == "bank"


def test_find_quote_rejects_changed_numbers_and_paraphrases():
    texts = {"a": "5G 프리미엄 요금제는 월 89,000원이며 데이터 150GB를 제공한다."}

    assert find_quote("5G 프리미엄 요금제는 월 89,000원이며 데이터 110GB를 제공한다.", texts) is None
    assert find_quote("프리미엄 요금제의 데이터는 아주 넉넉하게 제공된다.", texts) is None


def test_find_quote_normalizes_korean_document_characters():
    texts = {"a": "예금ㆍ적금의 중도해지 이율은 「연 ０.５％」를 적용한다."}

    assert find_quote("예금·적금의 중도해지 이율은 연 0.5%를 적용한다.", texts) == "a"


def test_missing_numbers_requires_statement_values_in_quote():
    assert missing_numbers("연 1.0%p가 더해진다", "연 1.0%p, 마케팅 수신에 동의하면") == []
    assert missing_numbers("최대 12일이다", "최대 11일이다") == ["12"]
    assert missing_numbers("1,000원이다", "1000원을 부과한다") == []


async def test_groundedness_checks_quotes_against_contexts():
    response = _json(
        _sentences(
            [
                _statement("입사 첫해에는 한 달 개근 시 하루가 생긴다.", "supported", quote="1개월 개근 시 1일의 유급휴가가 발생한다", context_id="c1"),
                _statement("입사 첫해 휴가는 최대 11일이다.", "supported", quote="최대 11일이다", context_id="[C1]"),
            ],
            [_statement("쓰지 않은 휴가는 다음 해로 자동 이월된다.", "supported", core=False, quote="미사용 휴가는 자동 이월된다", context_id="c2")],
        )
    )

    result, llm = await _measure("chaejeom.groundedness", response)

    assert result.score == 0.75
    assert [u.verdict for u in result.units] == ["supported", "supported", "unsupported"]
    assert result.units[1].context_ids == ["hr-12"]
    assert "찾지 못해" in result.units[2].reason
    assert [u.core for u in result.units] == [True, True, False]
    assert "[c1] 근로자가" in llm.prompt(0) and "[s2] 쓰지 않은 휴가는" in llm.prompt(0)
    assert "hr-11" not in llm.prompt(0)
    assert result.source.framework == "chaejeom" and result.raw_score is None


async def test_groundedness_without_statements_is_not_applicable():
    sample = SAMPLE.model_copy(update={"answer": "잘 모르겠습니다. 인사팀에 문의해 주세요."})

    result, _ = await _measure("chaejeom.groundedness", _json(_sentences([], [])), sample)

    assert result.score is None and result.error is None
    assert "판단할 사실 진술이 없어" in result.reason


async def test_context_relevance_marks_each_chunk():
    response = _json(
        {
            "question_target": "연차휴가",
            "chunks": [
                {"id": "c1", "about_target": True, "has_answer": True, "reason": "이유입니다."},
                {"id": "c2", "about_target": True, "has_answer": True, "reason": "이유입니다."},
                {"id": "c3", "about_target": False, "has_answer": False, "reason": "이유입니다."},
            ],
        }
    )

    result, _ = await _measure("chaejeom.context_relevance", response)

    assert result.score == 0.75
    assert [u.context_ids for u in result.units] == [["hr-11"], ["hr-12"], ["gen-05"]]
    assert "관련 2, 일부 관련 0, 관련 없음 1" in result.reason


async def test_context_relevance_asks_again_then_reports_missing_chunks():
    partial = _json({"chunks": [{"id": "c1", "about_target": True, "has_answer": True}]})
    llm = ScriptedLLM([partial, partial])

    result = await get_metric("chaejeom.context_relevance")(llm=llm).ameasure(SAMPLE)

    assert len(llm.calls) == 2 and "이전 응답에서 다음 번호가 빠졌습니다: c2, c3" in llm.prompt(1)
    assert result.score is None
    assert result.error == "판정에서 빠진 문맥 조각이 있습니다: c2, c3"


async def test_answer_relevance_ignores_made_up_irrelevant_parts():
    real = _answer(irrelevant_parts=["쓰지 않은 휴가는 다음 해로 자동 이월됩니다."])
    made_up = _answer(irrelevant_parts=["답변에 없는 문장"])
    evasive = _answer(evasive=True)

    assert (await _measure("chaejeom.answer_relevance", real))[0].score == 0.75
    assert (await _measure("chaejeom.answer_relevance", made_up))[0].score == 1.0
    result, _ = await _measure("chaejeom.answer_relevance", evasive)
    assert result.score == 0.0 and result.units[0].text.startswith("답을 피함")
    off_topic, _ = await _measure("chaejeom.answer_relevance", _answer(same_target=False))
    assert off_topic.score == 0.0 and off_topic.units[0].verdict == "off_topic"


def test_axis_average_leaves_out_chaejeom_metrics():
    responses = [
        _json(_sentences([_statement("휴가는 최대 11일이다.", "supported", quote="최대 11일이다", context_id="c2")], [])),
        _json({"statements": ["입사 첫해 휴가는 최대 11일이다."]}),
        _json({"statements": [{"statement": "입사 첫해 휴가는 최대 11일이다.", "reason": "문맥에 있습니다.", "verdict": 0}]}),
    ]
    # concurrency=1 keeps the scripted responses aligned with the call order.
    result = evaluate(
        [SAMPLE], ScriptedLLM(responses), metrics=["chaejeom.groundedness", "ragas.faithfulness"], concurrency=1, cache=False, repeats=1
    )

    row = result.by_axis["groundedness"]
    assert row["chaejeom"].mean == 1.0 and row["ragas"].mean == 0.0
    assert row["average"].mean == 0.0


async def test_groundedness_accepts_quotes_from_several_contexts():
    quote = "근로자가 입사 후 1년 미만인 경우 1개월 개근 시 1일의 유급휴가가 발생한다.\n입사 첫해에 발생하는 유급휴가는 최대 11일이다."
    response = _json(_sentences([_statement("한 달 개근마다 하루씩, 최대 11일이다.", "supported", quote=quote, context_id="c1,c2")], []))

    result, _ = await _measure("chaejeom.groundedness", response)

    assert result.units[0].verdict == "supported"
    assert result.units[0].context_ids == ["hr-11", "hr-12"]


def test_repeated_statement_with_split_evidence_is_merged():
    from chaejeom.metrics.chaejeom.groundedness import merge_repeated
    from chaejeom.metrics.chaejeom.schema import JudgedStatement

    statement = "입사 첫해에는 한 달 개근할 때마다 하루씩, 최대 11일까지 쓸 수 있다."
    repeated = [
        JudgedStatement(statement=statement, core=True, verdict="supported", context_id="c1", quote="1개월 개근 시 1일의 유급휴가가 발생한다."),
        JudgedStatement(statement=statement, core=True, verdict="supported", context_id="c2", quote="유급휴가는 최대 11일이다."),
        JudgedStatement(statement="자동 이월된다.", core=False, verdict="unsupported"),
    ]

    merged = merge_repeated(repeated)

    assert len(merged) == 2
    assert merged[0].context_id == "c1, c2" and missing_numbers(statement, merged[0].quote) == []


def test_prompts_carry_rules_combined_from_the_upstream_frameworks():
    from chaejeom.metrics.chaejeom.prompts import ANSWER_RELEVANCE, CONTEXT_RELEVANCE, GROUNDEDNESS

    # TruLens: a related topic is not support; every entity in the question must match; multi-part questions need every part.
    assert "비슷한 주제를 말할 뿐 진술 자체를 뒷받침하지 않으면" in GROUNDEDNESS
    assert "여러 조건을 함께 물으면 그 조건을 모두 만족해야 true" in CONTEXT_RELEVANCE
    assert "모두 직접 답해야 true 입니다. 일부만 답하면 false" in ANSWER_RELEVANCE
    # RAGAS: a noncommittal "it depends" counts as evasive.
    assert '"경우에 따라 다릅니다"처럼 어떤 경우인지 밝히지 않는 모호한 답도 true' in ANSWER_RELEVANCE
    # The only slots left are the inputs, so a domain rewrite can change the role line and procedure as plain text.
    assert "{role}" not in GROUNDEDNESS and "{reason_style}" not in ANSWER_RELEVANCE and "{example}" not in CONTEXT_RELEVANCE


async def test_missing_numbers_only_leave_a_note():
    statement = _statement("입사 첫해 휴가는 최대 11일이고, 3분기 기준이다.", "supported", quote="입사 첫해에 발생하는 유급휴가는 최대 11일이다", context_id="c2")
    llm = ScriptedLLM([_json(_sentences([statement], []))])

    result = await get_metric("chaejeom.groundedness")(llm=llm).ameasure(SAMPLE)

    unit = result.units[0]
    assert unit.verdict == "supported" and "확인 필요" in unit.reason and "3" in unit.reason


async def test_absence_statement_is_checked_against_contexts():
    honest = {**_statement("자료에서 3년 차 휴가 일수는 확인되지 않는다.", "supported"), "absence": True}
    missed = {**_statement("자료에서 입사 첫해 휴가 일수는 확인되지 않는다.", "contradicted", quote="입사 첫해에 발생하는 유급휴가는 최대 11일이다", context_id="c2"), "absence": True}
    llm = ScriptedLLM([_json(_sentences([honest], [])), _json(_sentences([missed], []))])
    metric = get_metric("chaejeom.groundedness")(llm=llm)

    first = await metric.ameasure(SAMPLE)
    second = await metric.ameasure(SAMPLE)

    # A true "not in the context" claim is supported without a quote; a false one is contradicted by quoting the chunk.
    assert (first.units[0].verdict, first.score) == ("supported", 1.0)
    assert (second.units[0].verdict, second.score) == ("contradicted", 0.0)


async def test_absence_judged_supported_stays_supported_even_with_a_nearby_quote():
    # Judges often quote a nearby figure (another period) while correctly finding the asked value absent,
    # so a quote alone must not turn a correct absence claim into a contradiction.
    honest = {**_statement("자료에서 3년 차 휴가 일수는 확인되지 않는다.", "supported", quote="입사 첫해에 발생하는 유급휴가는 최대 11일이다", context_id="c2"), "absence": True}
    result = await get_metric("chaejeom.groundedness")(llm=ScriptedLLM([_json(_sentences([honest], []))])).ameasure(SAMPLE)

    assert (result.units[0].verdict, result.score) == ("supported", 1.0)


async def test_absence_label_on_a_statement_that_does_not_say_anything_is_missing_is_ignored():
    # The judge marked a hedge as an absence claim; without a quote it must not pass as supported.
    hedge = {**_statement("휴가 일수는 상황에 따라 다를 수 있다.", "supported"), "absence": True}
    result = await get_metric("chaejeom.groundedness")(llm=ScriptedLLM([_json(_sentences([hedge], []))])).ameasure(SAMPLE)

    assert (result.units[0].verdict, result.score) == ("unsupported", 0.0)


async def test_declining_for_missing_information_is_not_scored_for_answer_relevance():
    response = _json(
        {"question_target": "3년 차 휴가", "answer_target": "3년 차 휴가", "declines_missing": True,
         "declines_quote": "제공된 자료에서는 3년 차 휴가 일수를 확인할 수 없습니다.", "evasive": False,
         "same_target": True, "discusses_asked": True, "answers_directly": False}
    )
    result = await get_metric("chaejeom.answer_relevance")(llm=ScriptedLLM([response])).ameasure(
        EvalSample(query="3년 차 휴가는 며칠인가요?", answer="제공된 자료에서는 3년 차 휴가 일수를 확인할 수 없습니다.")
    )

    assert result.score is None and result.error is None
    assert result.units[0].verdict == "declined"


async def test_declining_needs_a_sentence_the_answer_really_has():
    # The judge flagged "not in the materials", but the answer only talks about how to apply.
    response = _json(
        {"question_target": "장학금 성적 기준", "answer_target": "장학금 신청 방법", "declines_missing": True,
         "declines_quote": "자료에서 성적 기준을 확인할 수 없습니다.", "evasive": False,
         "same_target": True, "discusses_asked": False, "answers_directly": False}
    )
    result = await get_metric("chaejeom.answer_relevance")(llm=ScriptedLLM([response])).ameasure(
        EvalSample(query="장학금 성적 기준은 몇 점인가요?", answer="장학금은 개강 2주 전까지 학생 포털에서 신청하시면 됩니다.")
    )

    assert result.score == 0.25
    assert result.units[0].verdict == "other_aspect"


async def test_declining_needs_a_quote_that_says_something_is_missing():
    # The judge quoted a real answer sentence that is simply off topic; it does not say anything is missing.
    answer = "공항철도 일반열차는 모든 역에 정차하며 수하물 보관 서비스는 서울역에서 이용할 수 있습니다."
    response = _json(
        {"question_target": "직통열차 소요 시간", "answer_target": "일반열차 정차역", "declines_missing": True,
         "declines_quote": answer, "evasive": False, "same_target": False, "discusses_asked": False, "answers_directly": False}
    )
    result = await get_metric("chaejeom.answer_relevance")(llm=ScriptedLLM([response])).ameasure(
        EvalSample(query="공항철도 직통열차는 서울역에서 인천공항까지 얼마나 걸리나요?", answer=answer)
    )

    assert result.score == 0.0 and result.units[0].verdict == "off_topic"


def test_short_sentences_without_facts_join_the_next_one():
    from chaejeom.metrics.chaejeom.groundedness import join_short

    assert join_short(["네.", "3분기 매출은 86.1조 원입니다."]) == ["네. 3분기 매출은 86.1조 원입니다."]
    assert join_short(["매출은 늘었습니다.", "감사합니다."]) == ["매출은 늘었습니다. 감사합니다."]
    assert join_short(["3%.", "다음 문장입니다."]) == ["3%.", "다음 문장입니다."]
    assert join_short(["네."]) == ["네."]
