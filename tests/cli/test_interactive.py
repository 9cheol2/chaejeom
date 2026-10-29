import json

from fakes import ScriptedLLM
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from chaejeom.cli.banner import ptk_style
from chaejeom.cli.interactive import Session
from chaejeom.cli.interactive.command_input import read_command
from chaejeom.cli.picker import group, pick_metrics, pick_one, toggle_group
from chaejeom.config import EvalConfig

STATEMENTS = json.dumps({"statements": ["쓰지 않은 휴가는 이월된다."]}, ensure_ascii=False)
VERDICTS = json.dumps(
    {"statements": [{"statement": "쓰지 않은 휴가는 이월된다.", "reason": "문맥에 이월 규정이 없습니다.", "verdict": 0}]},
    ensure_ascii=False,
)


def _session(tmp_path, monkeypatch, responses=(), confirm=False):
    console = Console(record=True, width=100)
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: ScriptedLLM(list(responses)))
    if confirm:
        # Every picker returns its first option, which is "Start" in the /run confirmation.
        monkeypatch.setattr("chaejeom.cli.picker.pick_one", lambda title, options, current=None: options[0][0])
    data = tmp_path / "samples.jsonl"
    data.write_text(
        json.dumps({"id": "hr-1", "query": "연차 질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return Session(console, EvalConfig(runs=1)), console, data


def test_full_flow_data_metrics_run_show(tmp_path, monkeypatch):
    session, console, data = _session(tmp_path, monkeypatch, [STATEMENTS, VERDICTS], confirm=True)

    assert session.handle(str(data))
    assert session.handle("/metrics ragas.faithfulness")
    assert session.handle("/run")
    assert session.handle("/show hr-1")

    out = console.export_text()
    assert "1 samples" in out
    assert "Groundedness" in out and "RAGAS Faithfulness" in out
    assert "ragas.faithfulness" in out
    assert "✗ 쓰지 않은 휴가는 이월된다." in out
    assert "문맥에 이월 규정이 없습니다." in out
    assert list((tmp_path / "output").glob("*.json"))
    assert list((tmp_path / "output").glob("*.csv"))


def test_show_lists_samples_flags_unscored_ones_and_narrows_a_sample(tmp_path, monkeypatch):
    # The faithfulness judge finds no statements, so the sample gets no score.
    session, console, data = _session(tmp_path, monkeypatch, [json.dumps({"statements": []})], confirm=True)
    session.handle(str(data))
    session.handle("/metrics ragas.faithfulness")
    session.handle("/run")

    assert session.handle("/show")
    assert session.handle("/show hr-1 ragas")
    assert session.handle("/show hr-1 trulens")

    out = console.export_text()
    # The metric table shows 0/1 scored; the unscored table names the sample and the run count.
    assert "Samples without a score" in out and "0/1" in out and "1/1" in out
    assert "Samples, lowest average first" in out and "no score" in out
    assert "No metric matches trulens" in out


def test_errors_and_guidance(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)

    assert session.handle("/run")
    assert session.handle("/show 0")
    assert session.handle("/runs 0")
    assert session.handle("/data 없는파일.jsonl")
    assert session.handle("/뭐지")
    assert session.handle("/help")
    assert session.handle("/exit") is False

    out = console.export_text()
    assert "Load data first with /data" in out
    assert "No results yet" in out
    assert "whole number of 1 or more" in out
    assert "Usage" in out and "/data [file]" in out and "/effort [low|medium|high]" not in out and "/temperature [0-2]" in out
    assert "Unknown command" in out


def test_repeats_and_status(tmp_path, monkeypatch):
    session, _, data = _session(tmp_path, monkeypatch)
    session.handle(str(data))
    session.handle("/runs 3")

    session.handle("/metrics ragas.faithfulness")
    status = "\n".join("".join(text for text, _ in line) for line in session.status(100))

    assert session.repeats == 3
    words = status.split()
    assert words[:4] == ["model:", "gpt-4.1-mini", "temperature:", "0"]
    assert "[RAGAS]" in status and "[TruLens]" not in status
    assert words[-2:] == ["runs:", "3"]


def test_language_switch(tmp_path, monkeypatch):
    session, console, data = _session(tmp_path, monkeypatch, confirm=True)

    session.handle("/language ko")
    session.handle(str(data))
    session.handle("/metrics ragas.faithfulness")
    session.handle("/runs 2")
    session.handle("/run")
    session.handle("/language jp")
    session.handle("/language en")
    session.handle("/run")

    out = console.export_text()
    assert "언어: 한국어" in out
    assert "불러왔습니다:" in out and "샘플 1개" in out and "(query 1, contexts 1, answer 1)" in out
    assert "반복 횟수: 2회." in out
    assert "지원하지 않는 언어입니다: jp" in out
    assert "Language: English" in out
    assert session.config.language == "en"


def test_data_format_errors_show_guide(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)
    cases = {
        "notes.txt": "질문과 답변\n",
        "broken.jsonl": '{"query": "질문"}\n{"query": \n',
        "unknown.jsonl": '{"question": "질문", "answer": "답변"}\n',
        "nothing.jsonl": '{"id": "a", "metadata": {}}\n',
        "list.json": '{"query": "질문"}',
        "objects.json": '[{"query": "질문"}, "문장"]',
        "types.jsonl": '{"query": "질문", "contexts": "문맥 하나"}\n',
        "extra.csv": "query,answer\n질문,답변,남는 칸\n",
        "unknown.csv": "question,answer\n질문,답변\n",
        "contexts.csv": 'query,contexts\n질문,"[문맥"\n',
    }
    for name, text in cases.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
        session.handle(f"/data {tmp_path / name}")
    (tmp_path / "excel.csv").write_bytes("query,answer\n질문,답변\n".encode("cp949"))
    session.handle(f"/data {tmp_path / 'excel.csv'}")
    session.handle(f"/data {tmp_path / 'missing.jsonl'}")

    out = console.export_text()
    assert "notes.txt: unsupported file type. Use a JSONL, JSON or CSV file." in out
    assert "broken.jsonl line 2: not valid JSON" in out
    assert out.count("Moved question to metadata.") == 2
    assert "nothing.jsonl line 1: none of query, contexts or answer was found." in out
    assert "list.json: a JSON file must contain a list of samples." in out
    assert "objects.json sample 2: each sample must be a JSON object" in out
    assert "types.jsonl line 1: wrong value type in contexts." in out
    assert "extra.csv line 2: the row has more cells than the header." in out
    assert "contexts.csv" not in out
    assert "Read the file as CP949" in out
    assert out.count("Please provide the data in one of these formats.") == 7
    assert "id,query,context_1,context_2,answer" in out
    assert "File not found:" in out
    # The last file loaded is an Excel CSV saved as CP949.
    assert [s.query for s in session.samples] == ["질문"]


def test_csv_input(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)
    data = tmp_path / "samples.csv"
    data.write_text(
        "﻿id,query,context_1,context_2,answer,metadata.case\n"
        "hr-01,경조사 휴가는 며칠인가요?,본인 결혼 시 5일을 준다.,,5일입니다.,정확한 답변\n"
        ',재택은 며칠인가요?,"주 2일까지, 팀장 승인",식당은 11시 30분에 연다.,주 2일입니다.,\n'
        '3,질문만,,,,\n',
        encoding="utf-8",
    )
    json_contexts = tmp_path / "list.csv"
    json_contexts.write_text('query,contexts,answer\n질문,"[""문맥 1"", ""문맥 2""]",답변\n', encoding="utf-8")

    session.handle(f"/data {data}")
    first, second, third = session.samples
    session.handle(f"/data {json_contexts}")

    assert first.id == "hr-01" and [c.text for c in first.contexts] == ["본인 결혼 시 5일을 준다."]
    assert first.metadata == {"case": "정확한 답변"}
    assert second.id is None and [c.text for c in second.contexts] == ["주 2일까지, 팀장 승인", "식당은 11시 30분에 연다."]
    assert third.query == "질문만" and third.contexts == [] and third.answer == ""
    assert [c.text for c in session.samples[0].contexts] == ["문맥 1", "문맥 2"]
    assert "3 samples" in console.export_text()


def test_data_format_error_in_korean(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)
    (tmp_path / "notes.txt").write_text("query\n", encoding="utf-8")
    (tmp_path / "bad.jsonl").write_text('{"question": "질문"}\n', encoding="utf-8")

    session.handle("/language ko")
    session.handle(f"/data {tmp_path / 'notes.txt'}")
    session.handle(f"/data {tmp_path / 'bad.jsonl'}")

    out = console.export_text()
    assert "notes.txt: 지원하지 않는 파일 형식입니다. JSONL, JSON, CSV 파일로 넣어 주세요." in out
    assert "bad.jsonl 1번째 줄: query, contexts, answer 중 어느 것도 없습니다." in out
    assert "아래 형식 중 하나에 맞춰 데이터를 넣어 주세요." in out


def test_missing_field_warning(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)
    data = tmp_path / "no_answer.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"]}, ensure_ascii=False), encoding="utf-8")

    session.handle(f"/data {data}")

    assert "ragas.faithfulness: 1 samples are missing required inputs" in console.export_text()


def test_clean_reason_drops_score_line():
    from chaejeom.cli.views import clean_reason

    assert clean_reason("검색 결과가 질의에 답합니다.\n\nScore: 3") == "검색 결과가 질의에 답합니다."
    assert clean_reason("점수 3점을 줄 만합니다.") == "점수 3점을 줄 만합니다."


def test_ptk_style():
    assert ptk_style("bold #FFB347") == "bold fg:#FFB347"
    assert ptk_style("#AA0000 on #00BB00") == "bg:#00BB00 fg:#AA0000"
    assert ptk_style("") == ""


def test_read_command_returns_text(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path, monkeypatch)
    with create_pipe_input() as inp:
        inp.send_text("/help\r")
        with create_app_session(input=inp, output=DummyOutput()):
            assert read_command(session) == "/help"


def test_read_command_ctrl_d_exits(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path, monkeypatch)
    with create_pipe_input() as inp:
        inp.send_text("\x04")
        with create_app_session(input=inp, output=DummyOutput()):
            assert read_command(session) is None


UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"


def _pick(keys, selected=frozenset(), repeats=1):
    with create_pipe_input() as inp:
        inp.send_text(keys)
        with create_app_session(input=inp, output=DummyOutput()):
            return pick_metrics(set(selected), repeats)


def test_metric_grid_cell_row_column_and_runs():
    # The cursor starts on RAGAS faithfulness: toggle it, then the cell below.
    assert _pick(" " + DOWN + " \r") == ({"ragas.faithfulness", "ragas.context_relevance"}, 1)
    # An axis label in the left column toggles the whole axis.
    assert _pick(LEFT + " \r")[0] == {"ragas.faithfulness", "deepeval.faithfulness", "trulens.groundedness", "chaejeom.groundedness"}
    # A framework label in the top row toggles the whole framework; pressing it again clears it.
    assert _pick(RIGHT + UP + " \r")[0] == {"deepeval.faithfulness", "deepeval.contextual_relevancy", "deepeval.answer_relevancy"}
    assert _pick(UP + " \r", selected={"ragas.faithfulness", "ragas.context_relevance", "ragas.response_relevancy"})[0] == set()
    # "All" in the top-left corner selects every metric.
    assert len(_pick(UP + LEFT + " \r")[0]) == 12
    # The rightmost column holds the Chaejeom metrics.
    assert _pick(LEFT + LEFT + UP + " \r")[0] == {"chaejeom.groundedness", "chaejeom.context_relevance", "chaejeom.answer_relevance"}
    # Left/Right on the bottom "Runs" row change the repeat count.
    assert _pick(UP + UP + RIGHT + RIGHT + LEFT + "\r", repeats=2) == (set(), 3)
    assert _pick("\x1b") is None


def test_group_and_toggle():
    groundedness = {"ragas.faithfulness", "deepeval.faithfulness", "trulens.groundedness", "chaejeom.groundedness"}

    assert group(1, 0) == groundedness
    assert toggle_group(set(), groundedness) == groundedness
    assert toggle_group(groundedness, groundedness) == set()
    assert toggle_group({"ragas.faithfulness"}, groundedness) == groundedness


def test_model_and_embedding_commands(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)

    assert session.judge_setting() == ("temperature:", "0")

    session.handle("/model gpt-4.1-mini 0.3")
    assert session.config.judge_options() == {"temperature": 0.3}
    assert session.judge_setting() == ("temperature:", "0.3")

    session.handle("/model gpt-5-mini high")
    assert session.config.judge_options() == {"reasoning_effort": "high"}
    assert "".join(t for t, _ in session.status(100)[0]).split()[:4] == ["model:", "gpt-5-mini", "effort:", "high"]

    session.handle("/embedding text-embedding-3-small")
    assert session.config.embedding.model == "text-embedding-3-small"

    session.handle("/model claude-haiku-5-5")
    session.handle("/model gpt-4o-mini low")
    session.handle("/model gpt-5-mini 0")
    session.handle("/model gpt-4o-mini 3")
    out = console.export_text()
    assert "Unsupported judge model: claude-haiku-5-5" in out
    assert "gpt-4o-mini takes a temperature (0 to 2), not a reasoning effort" in out
    assert "gpt-5-mini is a reasoning model and takes a reasoning effort (low, medium, high), not a temperature" in out
    assert "Temperature must be between 0 and 2" in out
    assert session.config.judge.model == "gpt-5-mini"


def test_temperature_and_effort_commands_follow_model(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)

    assert "/temperature" in session.commands() and "/effort" not in session.commands()
    session.handle("/temperature 0.7")
    assert session.judge_setting() == ("temperature:", "0.7")
    session.handle("/effort low")

    session.handle("/model gpt-6-luna low")
    assert "/effort" in session.commands() and "/temperature" not in session.commands()
    session.handle("/effort high")
    assert session.judge_setting() == ("effort:", "high")
    session.handle("/temperature 0")

    out = console.export_text()
    assert "gpt-4.1-mini is not a reasoning model and has no reasoning effort. Use /temperature instead." in out
    assert "gpt-6-luna is a reasoning model and has no temperature. Use /effort instead." in out
    assert session.judge_setting() == ("effort:", "high")


def test_command_menu_and_enter_runs_first_match(tmp_path, monkeypatch):
    from prompt_toolkit.buffer import CompletionState
    from prompt_toolkit.completion import Completion
    from prompt_toolkit.document import Document

    from chaejeom.cli.interactive.command_input import command_menu

    state = CompletionState(Document("/"), [Completion("/data", -1), Completion("/metrics", -1)])
    text = "".join(t for _, t in command_menu(state))
    styles = [s for s, _ in command_menu(state)]

    assert "› /data" in text and "Load evaluation data" in text
    assert not any("bg:" in s for s in styles)

    session, _, _ = _session(tmp_path, monkeypatch)
    with create_pipe_input() as inp:
        inp.send_text("/he\r")
        with create_app_session(input=inp, output=DummyOutput()):
            assert read_command(session) == "/help"


def test_reasoning_model_defaults_to_low_effort():
    config = EvalConfig(judge={"provider": "openai", "model": "gpt-6-luna"})

    assert config.judge_options() == {"reasoning_effort": "low"}
    assert EvalConfig().judge_options() == {}


def test_model_picker_then_setting_picker(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path, monkeypatch)
    with create_pipe_input() as inp:
        # The cursor starts on the current model (gpt-4.1-mini); one row down is gpt-5-mini.
        inp.send_text("\x1b[B\r\r")
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle("/model")

    assert session.config.judge.model == "gpt-5-mini"
    assert session.config.judge_options() == {"reasoning_effort": "low"}


def test_pick_one_starts_at_current():
    options = [("a", ""), ("b", ""), ("c", "")]
    with create_pipe_input() as inp:
        inp.send_text("\x1b[B\r")
        with create_app_session(input=inp, output=DummyOutput()):
            assert pick_one("고르세요", options, current="b") == "c"


def test_data_without_path_opens_path_input(tmp_path, monkeypatch):
    session, console, data = _session(tmp_path, monkeypatch)
    with create_pipe_input() as inp:
        inp.send_text(f"{data}\r")
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle("/data")
    assert len(session.samples) == 1

    with create_pipe_input() as inp:
        inp.send_text("\x1b")
        with create_app_session(input=inp, output=DummyOutput()):
            session.handle("/config")
    assert "Cancelled." in console.export_text()


def test_path_suggestions_render_without_background(tmp_path):
    from prompt_toolkit.buffer import CompletionState
    from prompt_toolkit.completion import Completion
    from prompt_toolkit.document import Document

    from chaejeom.cli.picker import suggestion_menu

    state = CompletionState(Document("sa"), [Completion("samples.jsonl", -2), Completion("samples.csv", -2)], complete_index=1)
    fragments = suggestion_menu(state)

    assert "".join(text for _, text in fragments) == "     samples.jsonl\n   › samples.csv\n"
    assert not any("bg:" in style for style, _ in fragments)


def test_language_switch_redraws_start_screen(tmp_path, monkeypatch):
    session, console, data = _session(tmp_path, monkeypatch)
    session.handle(str(data))

    session.handle("/language ko")

    out = console.export_text()
    assert "안녕하세요, 한국어 RAG 평가기 채점입니다." in out
    assert out.index("안녕하세요") < out.index("언어: 한국어")
    assert len(session.samples) == 1


def test_bare_command_words_are_not_read_as_paths(tmp_path, monkeypatch):
    session, console, _ = _session(tmp_path, monkeypatch)

    assert session.handle("help")
    assert session.handle("exit") is False

    assert "Did you mean /help?" in console.export_text()


def test_run_limit_and_all_failed_run_is_not_saved(tmp_path, monkeypatch):
    session, console, data = _session(tmp_path, monkeypatch, ["x"] * 3, confirm=True)
    session.handle(str(data))
    session.handle("/metrics ragas.faithfulness")

    session.handle("/run 0")
    session.handle("/run 1")

    out = console.export_text()
    assert "/run 20" in out
    assert "Every evaluation failed" in out
    assert not (tmp_path / "output").exists()


def test_ctrl_c_during_run_keeps_the_session(tmp_path, monkeypatch):
    from chaejeom.cli.interactive import run as run_commands

    async def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    session, console, data = _session(tmp_path, monkeypatch, confirm=True)
    monkeypatch.setattr(run_commands, "aevaluate", interrupted)
    session.handle(str(data))
    session.handle("/metrics ragas.faithfulness")

    assert session.handle("/run")
    assert "Evaluation stopped" in console.export_text() and len(session.samples) == 1


def test_config_save_round_trips(tmp_path, monkeypatch):
    from chaejeom.config import load_config

    session, console, _ = _session(tmp_path, monkeypatch)
    session.handle("/metrics ragas.faithfulness,chaejeom.groundedness")
    session.handle("/runs 3")

    session.handle(f"/config save {tmp_path / 'mine.yaml'}")

    loaded = load_config(tmp_path / "mine.yaml")
    assert loaded.metrics == ["ragas.faithfulness", "chaejeom.groundedness"] and loaded.runs == 3
    assert "Saved the current settings to" in console.export_text()


def test_status_shows_missing_domain_and_custom_prompt(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path, monkeypatch)
    session.domain_path = str(tmp_path / "gone.yaml")
    session.prompt_paths = {"chaejeom.groundedness": "p.yaml"}

    status = "\n".join("".join(text for text, _ in line) for line in session.status(120))

    assert "not found:" in status and "gone.yaml" in status
    assert "prompt:" in status and "custom (groundedness)" in status


def test_running_with_general_criteria_leaves_the_broken_domain_file_out(tmp_path, monkeypatch):
    response = json.dumps({"evasive": False, "same_target": True, "discusses_asked": True, "answers_directly": True})
    session, console, data = _session(tmp_path, monkeypatch, [response])
    session.domain_path = str(tmp_path / "gone.yaml")
    # "Run with general criteria" at the domain question, the first option ("Start") everywhere else.
    monkeypatch.setattr(
        "chaejeom.cli.picker.pick_one",
        lambda title, options, current=None: "general" if any(key == "general" for key, _ in options) else options[0][0],
    )
    session.handle(str(data))
    session.handle("/metrics chaejeom.answer_relevance")

    assert session.handle("/run")

    assert session.result is not None and session.result.metrics["chaejeom.answer_relevance"]["domain"] is None
    assert "gone.yaml" not in console.export_text()


def test_prompt_view_is_a_summary_with_inputs():
    from chaejeom.cli.views import prompt_text
    from chaejeom.metrics.chaejeom.prompts import preview

    text = preview("chaejeom.answer_relevance")
    summary = prompt_text(text, full=False)

    assert len(summary.splitlines()) < len(text.splitlines())
    assert "Inputs: {query}, {answer}" in summary
    assert prompt_text("x" * 500, full=True).endswith("(500 characters, folded)")


def test_enter_runs_a_prefix_only_when_it_matches_one_command(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path, monkeypatch)

    with create_pipe_input() as inp:
        inp.send_text("/he\r")
        with create_app_session(input=inp, output=DummyOutput()):
            assert read_command(session) == "/help"
    with create_pipe_input() as inp:
        # "/r" matches both /run and /runs, so Enter is ignored until the input is completed to "/run".
        inp.send_text("/r\run\r")
        with create_app_session(input=inp, output=DummyOutput()):
            assert read_command(session) == "/run"
