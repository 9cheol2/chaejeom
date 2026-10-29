import json

import pytest
from fakes import ScriptedLLM
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from chaejeom.cli.interactive import Session
from chaejeom.config import EvalConfig, apply_domain
from chaejeom.customize.domain import (
    DomainProfile,
    changed_lines,
    find_values,
    load_profile,
    organize,
    save_profile,
)
from chaejeom.customize.prompt_file import PromptFile, save_prompt
from chaejeom.metrics import get_metric
from chaejeom.metrics.chaejeom.prompts import TEMPLATES
from chaejeom.schema import EvalSample

SERVICE = "투자자가 상장사 실적과 공시를 묻는 금융 정보 챗봇"
RULE = "메모리 반도체를 물으면 D램, 낸드, HBM으로 답해도 같은 대상이다. 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다."
PROFILE = DomainProfile(
    name="금융 정보",
    service=SERVICE,
    groundedness="실적 수치는 기간, 단위, 연결/별도 기준까지 문맥과 같아야 맞는 것으로 본다.",
    answer_relevance=RULE,
)
ROLE = "당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다."


def _draft(**items):
    full = {key: "" for key in ("service", "groundedness", "context_relevance", "answer_relevance")}
    full.update(items)
    return json.dumps({"name": "금융 정보", "items": full, "removed_facts": [], "out_of_scope": []}, ensure_ascii=False)


def test_profile_round_trip_and_fingerprint(tmp_path):
    path = save_profile(PROFILE, tmp_path / "domains" / "finance.yaml")

    assert load_profile(path) == PROFILE
    assert len(PROFILE.fingerprint()) == 12
    assert PROFILE.fingerprint() != PROFILE.model_copy(update={"answer_relevance": "다른 기준"}).fingerprint()
    # The name is a label, not a criterion, so renaming does not make results incomparable.
    assert PROFILE.fingerprint() == PROFILE.model_copy(update={"name": "다른 이름"}).fingerprint()


def test_numbered_rules_stay_on_one_line_each():
    from chaejeom.metrics.chaejeom.prompts import _bullets

    rules = "기준은 다음과 같다. 1. 기간이 같아야 한다. 2. 수익률 3.5% 이상은 높은 것으로 본다."

    assert _bullets(rules) == "- 기준은 다음과 같다.\n- 1. 기간이 같아야 한다.\n- 2. 수익률 3.5% 이상은 높은 것으로 본다."


def test_load_rejects_the_earlier_format(tmp_path):
    old = tmp_path / "old.yaml"
    old.write_text("name: 인사\ncritical_info: 휴가 일수\n", encoding="utf-8")

    with pytest.raises(ValueError, match="예전 형식"):
        load_profile(old)


def test_domain_names_the_service_and_adds_the_rules_word_for_word():
    answer = PROFILE.template("chaejeom.answer_relevance")
    context = PROFILE.template("chaejeom.context_relevance")

    assert answer.startswith(f"당신은 다음 서비스의 답변을 평가하는 평가자입니다: {SERVICE}")
    rules = "[이 도메인의 판정 기준]\n아래 기준이 위 [절차]와 다르면 아래 기준을 따릅니다."
    block = answer[answer.index(rules) : answer.index("[출력 형식]")]
    assert "- 메모리 반도체를 물으면 D램, 낸드, HBM으로 답해도 같은 대상이다.\n- 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다." in block
    # A metric without rules only gets the role line; the rest of the prompt is the built-in one.
    assert context == TEMPLATES["chaejeom.context_relevance"].replace(ROLE, f"당신은 다음 서비스의 답변을 평가하는 평가자입니다: {SERVICE}")
    assert DomainProfile(name="빈 도메인").template("chaejeom.groundedness") is None
    # Braces in the user's words cannot break the template.
    braced = DomainProfile(name="x", groundedness="{회사} 이름은 정확해야 한다.").template("chaejeom.groundedness")
    assert "{회사}" in braced.format(query="q", contexts="c", sentences="s")


def test_changed_lines_are_the_role_line_and_the_added_rules():
    changes = changed_lines("chaejeom.answer_relevance", PROFILE.template("chaejeom.answer_relevance"))

    assert changes[0] == ("-", ROLE) and ("+", "- 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다.") in changes
    assert {sign for sign, _ in changes[1:]} == {"+"}


def test_find_values_catches_answers_not_types():
    assert find_values("경조사 휴가는 5일, 수수료는 3.5%, 2026년 1월 시행") == ["5일", "3.5%", "2026년"]
    assert find_values("2026-01-15 개정") == ["2026-01"]
    assert find_values("휴가 일수, 수수료율, 시행일") == []


async def test_organize_keeps_what_the_user_wrote_without_judging_it():
    llm = ScriptedLLM([_draft(service=SERVICE, answer_relevance=RULE)])

    draft = await organize(llm, "금융 정보 챗봇이에요. 메모리 반도체를 물으면 HBM으로 답해도 돼요.")

    assert draft.to_profile() == DomainProfile(name="금융 정보", service=SERVICE, answer_relevance=RULE)
    assert len(llm.calls) == 1
    assert "충분" not in llm.prompt(0) and "말한 수준 그대로" in llm.prompt(0)


async def test_organize_asks_once_more_when_values_remain():
    llm = ScriptedLLM([_draft(groundedness="영업이익은 32조원이다"), _draft(groundedness="영업이익 수치는 문맥과 같아야 한다")])

    draft = await organize(llm, "영업이익은 32조원이에요.")

    assert draft.item("groundedness") == "영업이익 수치는 문맥과 같아야 한다" and draft.removed_facts == ["32조원"]
    assert "[다시 정리하기]" in llm.prompt(1) and "32조원" in llm.prompt(1)

    # Values that survive the second pass are kept rather than cut out of the sentence; the CLI asks the user to rewrite them.
    stubborn = ScriptedLLM([_draft(groundedness="수수료 3%")] * 2)
    draft = await organize(stubborn, "수수료는 3%")
    assert draft.item("groundedness") == "수수료 3%" and draft.values() == ["3%"]


def test_apply_domain_only_touches_chaejeom_metrics():
    selected = {"ragas.faithfulness": {}, "chaejeom.groundedness": {}, "chaejeom.answer_relevance": {"domain": "other.yaml"}}

    applied = apply_domain(selected, "hr.yaml")

    assert applied == {
        "ragas.faithfulness": {},
        "chaejeom.groundedness": {"domain": "hr.yaml"},
        "chaejeom.answer_relevance": {"domain": "other.yaml"},
    }
    assert apply_domain(selected, None) is selected


async def test_metric_uses_the_domain_prompt_and_a_custom_prompt_wins(tmp_path):
    path = save_profile(PROFILE, tmp_path / "finance.yaml")
    response = json.dumps(
        {"question_target": "메모리 반도체", "answer_target": "HBM", "evasive": False, "same_target": True, "discusses_asked": True, "answers_directly": True},
        ensure_ascii=False,
    )
    sample = EvalSample(query="메모리 반도체 업황 어때요?", answer="HBM 수요가 늘고 있습니다.")
    metric = get_metric("chaejeom.answer_relevance")

    llm = ScriptedLLM([response])
    result = await metric(llm=llm, options={"domain": str(path)}).ameasure(sample)
    assert result.score == 1.0
    assert llm.prompt(0).startswith(f"당신은 다음 서비스의 답변을 평가하는 평가자입니다: {SERVICE}") and "[이 도메인의 판정 기준]" in llm.prompt(0)

    custom = save_prompt(PromptFile(metric="chaejeom.answer_relevance", template=TEMPLATES["chaejeom.answer_relevance"]), tmp_path / "p.yaml")
    llm = ScriptedLLM([response])
    await metric(llm=llm, options={"domain": str(path), "prompt": str(custom)}).ameasure(sample)
    assert llm.prompt(0).startswith(ROLE) and "[이 도메인의 판정 기준]" not in llm.prompt(0)


def _session(tmp_path, monkeypatch, responses=()):
    console = Console(record=True, width=160)
    # A new client is created for each organize and build call; return the same fake so the scripted responses continue.
    llm = ScriptedLLM(list(responses))
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: llm)
    monkeypatch.setattr(EvalConfig, "create_domain_llm", lambda self: llm)
    return Session(console, EvalConfig()), console


def test_domain_command_loads_shows_and_turns_off(tmp_path, monkeypatch):
    session, console = _session(tmp_path, monkeypatch)
    path = save_profile(PROFILE, tmp_path / "finance.yaml")

    session.handle(f"/domain {path}")
    status = "\n".join("".join(text for text, _ in line) for line in session.status(120))
    session.handle("/domain off")

    out = console.export_text()
    assert "domain: 금융 정보" in out and "answer_relevance" in out and "메모리 반도체를 물으면" in out
    assert ["domain:", "금융", "정보"] in [line.split() for line in status.splitlines()]
    assert session.domain_path is None and "Domain turned off" in out


def test_build_domain_organizes_shows_changes_and_saves(tmp_path, monkeypatch):
    response = _draft(service=SERVICE, groundedness=PROFILE.groundedness, answer_relevance=RULE)
    session, console = _session(tmp_path, monkeypatch, [response])
    keys = (
        "\r"  # menu: create from a description
        "금융 정보 챗봇이에요\r"  # description
        "\r"  # save
        "\r"  # default path
    )
    monkeypatch.chdir(tmp_path)
    with create_pipe_input() as inp:
        inp.send_text(keys)
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle("/domain")

    assert load_profile(session.domain_path) == PROFILE and session.domain_path.endswith("금융-정보.yaml")
    out = console.export_text()
    assert "Changed lines in the chaejeom.answer_relevance prompt" in out and "+ - 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다." in out


def test_run_asks_for_domain_when_chaejeom_metrics_have_none(tmp_path, monkeypatch):
    session, console = _session(tmp_path, monkeypatch)
    data = tmp_path / "samples.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False), encoding="utf-8")
    session.handle(str(data))
    session.handle("/metrics chaejeom.*")

    with create_pipe_input() as inp:
        inp.send_text("\x1b[B\x1b[B\r")  # cancel
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle("/run")

    assert session.result is None and "Cancelled." in console.export_text()


def test_domain_model_is_separate_from_judge():
    config = EvalConfig()

    assert config.domain_model.model == "gpt-4.1-mini" and config.judge.model == "gpt-4.1-mini"
    from chaejeom.config import model_options

    assert model_options(EvalConfig(domain_model={"provider": "openai", "model": "gpt-5-mini"}).domain_model) == {"reasoning_effort": "low"}
