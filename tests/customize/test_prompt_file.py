import json

import pytest
from fakes import ScriptedLLM
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from chaejeom.cli.interactive import Session
from chaejeom.config import EvalConfig, apply_prompts
from chaejeom.customize.prompt_file import (
    PromptFile,
    PromptRevisionError,
    check_template,
    is_editable,
    load_prompt,
    revise,
    save_prompt,
)
from chaejeom.metrics import get_metric, list_metrics
from chaejeom.metrics.catalog import upstream_prompts
from chaejeom.metrics.chaejeom.prompts import ANSWER_RELEVANCE, TEMPLATES
from chaejeom.schema import EvalSample

METRIC = "chaejeom.answer_relevance"
EXTRA = "- 금리 상품 질문에서는 숫자 없이 답하면 직접 답한 것으로 보지 않습니다."
EDITED = ANSWER_RELEVANCE.replace("- 반드시 JSON 만 출력하세요.\n", "- 반드시 JSON 만 출력하세요.\n" + EXTRA + "\n")


def _revision(template: str, summary: str = "원칙 한 줄을 더했습니다.") -> str:
    return json.dumps({"template": template, "summary": summary}, ensure_ascii=False)


def test_default_templates_pass_and_broken_ones_are_named():
    assert all(check_template(m, TEMPLATES[m]) == [] for m in TEMPLATES)
    assert check_template(METRIC, EDITED) == []

    problems = check_template(METRIC, EDITED.replace("{answer}", "답변"))
    assert any("{answer}" in p for p in problems)
    assert any("{extra}" in p for p in check_template(METRIC, EDITED + "{extra}"))
    assert any("[평가 지표]" in p for p in check_template(METRIC, EDITED.replace("답변 관련성:", "답변 품질:")))
    assert any("[출력 형식]" in p for p in check_template(METRIC, EDITED.replace('"evasive": false', '"evasive": 0')))
    assert check_template(METRIC, EDITED + "{")  # unbalanced brace


def test_only_chaejeom_metrics_are_editable_and_upstream_prompts_are_listed():
    upstream = [m for m in list_metrics() if not m.startswith("chaejeom.")]

    assert [m for m in list_metrics() if is_editable(m)] == sorted(TEMPLATES)
    for metric_id in upstream:
        steps = upstream_prompts(metric_id)
        assert steps and all(title and text for title, text in steps)


async def test_revise_retries_until_rules_are_kept():
    llm = ScriptedLLM([_revision(EDITED.replace("{answer}", "답변")), _revision(EDITED)])

    revision = await revise(llm, METRIC, ANSWER_RELEVANCE, "금리는 숫자로 답해야 직접 답한 것으로 봐 주세요")

    assert revision.template == EDITED
    assert "[다시 고치기]" in llm.prompt(1) and "{answer}" in llm.prompt(1)
    assert "금리는 숫자로 답해야" in llm.prompt(0)


async def test_revise_gives_up_after_three_attempts():
    llm = ScriptedLLM([_revision("고친 프롬프트")] * 3)

    with pytest.raises(PromptRevisionError):
        await revise(llm, METRIC, ANSWER_RELEVANCE, "요청")


def test_prompt_file_round_trip_and_checks(tmp_path):
    path = save_prompt(PromptFile(metric=METRIC, requests=["요청"], template=EDITED), tmp_path / "p.yaml")

    assert "template: |" in path.read_text(encoding="utf-8")
    assert load_prompt(path, METRIC).template == EDITED
    with pytest.raises(ValueError, match="chaejeom.groundedness"):
        load_prompt(path, "chaejeom.groundedness")
    broken = save_prompt(PromptFile(metric=METRIC, template="{query}"), tmp_path / "broken.yaml")
    with pytest.raises(ValueError, match="자리 표시"):
        load_prompt(broken)
    # A misspelled key is an error, not silently dropped.
    typo = tmp_path / "typo.yaml"
    typo.write_text(path.read_text(encoding="utf-8").replace("requests:", "request:"), encoding="utf-8")
    with pytest.raises(ValueError, match="request"):
        load_prompt(typo)


async def test_metric_judges_with_custom_prompt(tmp_path):
    path = save_prompt(PromptFile(metric=METRIC, template=EDITED), tmp_path / "p.yaml")
    response = json.dumps(
        {"question_target": "금리", "answer_target": "금리", "evasive": False, "same_target": True, "discusses_asked": True, "answers_directly": True},
        ensure_ascii=False,
    )
    llm = ScriptedLLM([response])

    result = await get_metric(METRIC)(llm=llm, options={"prompt": str(path)}).ameasure(EvalSample(query="금리는?", answer="연 3%입니다."))

    assert result.score == 1.0
    assert EXTRA in llm.prompt(0) and "연 3%입니다." in llm.prompt(0)


def test_apply_prompts_only_touches_listed_metrics():
    selected = {"ragas.faithfulness": {}, METRIC: {"domain": "d.yaml"}}

    assert apply_prompts(selected, {METRIC: "p.yaml"}) == {"ragas.faithfulness": {}, METRIC: {"prompt": "p.yaml", "domain": "d.yaml"}}
    assert apply_prompts(selected, {}) is selected


def _session(monkeypatch, responses=()):
    console = Console(record=True, width=140)
    llm = ScriptedLLM(list(responses))
    monkeypatch.setattr(EvalConfig, "create_domain_llm", lambda self: llm)
    return Session(console, EvalConfig()), console


def test_upstream_prompt_is_read_only(monkeypatch):
    session, console = _session(monkeypatch)

    session.handle("/prompt ragas.faithfulness")

    out = console.export_text()
    assert "ragas.faithfulness · Statement generation" in out and "ragas.faithfulness · Verdict" in out
    assert "read-only" in out


def test_edit_saves_custom_prompt_and_run_uses_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session, console = _session(monkeypatch, [_revision(EDITED)])

    with create_pipe_input() as inp:
        inp.send_text("\r" "금리는 숫자로 답해야 직접 답한 것으로 봐 주세요\r")  # menu: edit by request
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle(f"/prompt {METRIC}")

    out = console.export_text()
    saved = load_prompt(tmp_path / "prompts" / f"{METRIC}.yaml", METRIC)
    assert saved.template == EDITED and saved.requests == ["금리는 숫자로 답해야 직접 답한 것으로 봐 주세요"]
    assert f"{METRIC} · custom" in out and "Changes: 원칙 한 줄을 더했습니다." in out and "Saved to" in out
    assert session.metric_options()[METRIC]["prompt"].endswith(f"{METRIC}.yaml")


def test_load_by_file_and_reset(tmp_path, monkeypatch):
    session, console = _session(monkeypatch)
    path = save_prompt(PromptFile(metric=METRIC, template=EDITED), tmp_path / "p.yaml")

    session.handle(f"/prompt {path}")
    assert session.prompt_paths == {METRIC: str(path)}

    with create_pipe_input() as inp:
        inp.send_text("\x1b[B\x1b[B\r")  # menu: reset to the default prompt
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle(f"/prompt {METRIC}")

    assert session.prompt_paths == {}
    assert "uses the default prompt again" in console.export_text()
