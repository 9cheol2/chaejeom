import json

import pytest
from fakes import ScriptedLLM

from chaejeom.cli.main import main
from chaejeom.config import EvalConfig

STATEMENTS = json.dumps({"statements": ["진술 1"]}, ensure_ascii=False)

VERDICTS = json.dumps({"statements": [{"statement": "진술 1", "reason": "있음", "verdict": 1}]}, ensure_ascii=False)

TWO_STATEMENTS = json.dumps({"statements": ["진술 1", "진술 2"]}, ensure_ascii=False)
HALF_SUPPORTED = json.dumps(
    {
        "statements": [
            {"statement": "진술 1", "reason": "있음", "verdict": 1},
            {"statement": "진술 2", "reason": "없음", "verdict": 0},
        ]
    },
    ensure_ascii=False,
)


def _run_cli(tmp_path, monkeypatch, llm, *extra):
    config = tmp_path / "eval.yaml"
    config.write_text("metrics: [ragas.faithfulness]\nconcurrency: 1\nruns: 1\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    rows = [{"id": f"s{i}", "query": "질문", "contexts": ["문맥"], "answer": "답변"} for i in range(3)]
    data.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: llm)
    return main(["run", "--config", str(config), "--data", str(data), *extra])

def test_cli_does_not_save_and_fails_when_every_evaluation_failed(tmp_path, monkeypatch, capsys):
    code = _run_cli(tmp_path, monkeypatch, ScriptedLLM(["x"] * 9), "--out", str(tmp_path / "r.json"))

    assert code == 1 and not (tmp_path / "r.json").exists()
    assert "Every evaluation failed" in capsys.readouterr().err

def test_cli_limit_label_and_csv_out_name(tmp_path, monkeypatch):
    code = _run_cli(tmp_path, monkeypatch, ScriptedLLM([STATEMENTS, VERDICTS]), "--limit", "1", "--label", "v2", "--out", str(tmp_path / "r.csv"))

    saved = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert code == 0 and (tmp_path / "r.csv").exists()
    assert saved["label"] == "v2" and len(saved["samples"]) == 1

def test_compare_shows_axis_deltas_changed_samples_and_warnings(tmp_path, monkeypatch, capsys):
    before, after = tmp_path / "before.json", tmp_path / "after.json"
    unsupported = json.dumps({"statements": [{"statement": "진술 1", "reason": "없음", "verdict": 0}]}, ensure_ascii=False)
    _run_cli(tmp_path, monkeypatch, ScriptedLLM([STATEMENTS, VERDICTS]), "--limit", "1", "--out", str(before))
    _run_cli(tmp_path, monkeypatch, ScriptedLLM([STATEMENTS, unsupported] * 2), "--limit", "2", "--out", str(after), "--no-cache")
    capsys.readouterr()

    assert main(["compare", str(before), str(after)]) == 0

    out = capsys.readouterr().out
    assert "1.00 → 0.00 -1.00" in out
    assert "s0" in out and "ragas.faithfulness" in out
    assert "different data" in out and "1 samples appear in only one" in out

def test_compare_does_not_diff_averages_over_different_metrics(tmp_path, monkeypatch, capsys):
    before, after = tmp_path / "before.json", tmp_path / "after.json"
    _run_cli(tmp_path, monkeypatch, ScriptedLLM([STATEMENTS, VERDICTS]), "--limit", "1", "--out", str(before))
    # Add a second groundedness metric to the saved result so the axis mean averages two metrics.
    saved = json.loads(before.read_text(encoding="utf-8"))
    extra = {**saved["summary"][0], "metric_id": "deepeval.faithfulness", "mean": 0.0}
    saved["summary"].append(extra)
    saved["metrics"]["deepeval.faithfulness"] = {}
    saved["by_axis"]["groundedness"]["average"]["mean"] = 0.5
    after.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()

    assert main(["compare", str(before), str(after)]) == 0

    out = capsys.readouterr().out
    assert "Metrics in only one file: deepeval.faithfulness" in out
    assert "1.00 → 0.50 -" in out and "-0.50" not in out


def test_embeddings_not_created_when_not_needed(tmp_path, monkeypatch):
    config = tmp_path / "eval.yaml"
    config.write_text("judge: {provider: openai, model: gpt-4.1-mini}\nmetrics: [ragas.faithfulness]\nconcurrency: 1\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: ScriptedLLM([STATEMENTS, VERDICTS]))
    monkeypatch.setattr(EvalConfig, "create_embeddings", lambda self: pytest.fail("임베딩을 만들면 안 됨"))
    monkeypatch.chdir(tmp_path)

    assert main(["run", "--config", str(config), "--data", str(data), "--out", str(tmp_path / "r.json")]) == 0


def test_cli_run_writes_result(tmp_path, monkeypatch, capsys):
    config = tmp_path / "eval.yaml"
    config.write_text("judge: {provider: openai, model: gpt-5}\nmetrics: [ragas.faithfulness]\nconcurrency: 1\nruns: 1\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "result.json"
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: ScriptedLLM([TWO_STATEMENTS, HALF_SUPPORTED]))
    monkeypatch.chdir(tmp_path)

    code = main(["run", "--config", str(config), "--data", str(data), "--out", str(out)])

    assert code == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["summary"][0]["mean"] == 0.5
    assert saved["samples"][0]["results"][0]["units"][0]["text"] == "진술 1"
    assert "ragas.faithfulness" in capsys.readouterr().out


def test_cli_reports_missing_api_key(tmp_path, monkeypatch, capsys):
    config = tmp_path / "eval.yaml"
    config.write_text("judge: {provider: openai, model: gpt-5}\npreset: rag-triad\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    code = main(["run", "--config", str(config), "--data", str(data)])

    assert code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_cli_reports_config_error(tmp_path, capsys):
    config = tmp_path / "eval.yaml"
    config.write_text("judge: {provider: openai, model: gpt-5}\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    data.write_text("", encoding="utf-8")

    code = main(["run", "--config", str(config), "--data", str(data)])

    assert code == 1
    assert "하나 이상" in capsys.readouterr().err


def test_cli_reads_the_only_input_file_and_names_results_after_it(tmp_path, monkeypatch, capsys):
    config = tmp_path / "eval.yaml"
    config.write_text("metrics: [ragas.faithfulness]\nconcurrency: 1\nruns: 1\n", encoding="utf-8")
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: ScriptedLLM([TWO_STATEMENTS, HALF_SUPPORTED]))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "input").mkdir()

    assert main(["run", "--config", str(config)]) == 2
    assert "input/" in capsys.readouterr().err

    sample = json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False)
    (tmp_path / "input" / "hr.jsonl").write_text(sample, encoding="utf-8")
    assert main(["run", "--config", str(config)]) == 0
    saved = sorted(p.name for p in (tmp_path / "output").iterdir())
    assert len(saved) == 2 and saved[0].startswith("hr_") and saved[0].endswith(".csv") and saved[1] == saved[0][:-4] + ".json"


def test_result_paths_use_the_data_file_name_and_time():
    from datetime import datetime
    from pathlib import Path

    from chaejeom.cli.folders import result_paths

    json_path, csv_path = result_paths(Path("input/sample.csv"), datetime(2026, 10, 28, 15, 30, 12))

    assert json_path == Path("output/sample_20261028-153012.json") and csv_path == Path("output/sample_20261028-153012.csv")


def test_result_names_keep_dots_in_the_data_file_name():
    from datetime import datetime
    from pathlib import Path

    from chaejeom.cli.folders import result_paths
    from chaejeom.cli.main import _output_paths

    json_path, csv_path = result_paths(Path("input/samples.v2.jsonl"), datetime(2026, 10, 28, 15, 30, 12))

    assert json_path == Path("output/samples.v2_20261028-153012.json") and csv_path == Path("output/samples.v2_20261028-153012.csv")
    assert _output_paths("out/run.v2") == (Path("out/run.v2.json"), Path("out/run.v2.csv"))
    assert _output_paths("out/run.v2.csv") == (Path("out/run.v2.json"), Path("out/run.v2.csv"))
    assert _output_paths("result") == (Path("result.json"), Path("result.csv"))
