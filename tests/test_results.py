import csv
import json

import pytest
from fakes import ScriptedLLM

from chaejeom import evaluate
from chaejeom.schema import EvalSample

STATEMENTS = json.dumps({"statements": ["진술 1", "진술 2"]}, ensure_ascii=False)


def _verdicts(*values):
    items = [{"statement": f"진술 {i}", "reason": "이유", "verdict": v} for i, v in enumerate(values, start=1)]
    return json.dumps({"statements": items}, ensure_ascii=False)


def _read(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "엑셀용 UTF-8 BOM 이 있어야 함"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_csv_one_row_per_sample(tmp_path):
    samples = [
        EvalSample(id="hr-1", query="연차 질문", contexts=["문맥"], answer="답변", metadata={"model": "A"}),
        EvalSample(query="재택 질문", answer="답변"),
    ]
    llm = ScriptedLLM([STATEMENTS, _verdicts(1, 0)])
    result = evaluate(samples, llm, metrics=["ragas.faithfulness"], concurrency=1, repeats=1)

    rows = _read(result.to_csv(tmp_path / "result.csv"))

    assert list(rows[0]) == ["index", "id", "query", "meta.model", "ragas.faithfulness", "axis.groundedness", "errors"]
    assert rows[0]["id"] == "hr-1"
    assert rows[0]["query"] == "연차 질문"
    assert rows[0]["meta.model"] == "A"
    assert float(rows[0]["ragas.faithfulness"]) == 0.5
    assert float(rows[0]["axis.groundedness"]) == 0.5
    assert rows[1]["ragas.faithfulness"] == ""
    assert "contexts" in rows[1]["errors"]


def test_csv_with_repeats_has_std_columns(tmp_path):
    llm = ScriptedLLM([STATEMENTS, _verdicts(1, 0), STATEMENTS, _verdicts(1, 1)])
    sample = EvalSample(query="질문", contexts=["문맥"], answer="답변")
    result = evaluate([sample], llm, metrics=["ragas.faithfulness"], repeats=2, concurrency=1)

    rows = _read(result.to_csv(tmp_path / "result.csv"))

    assert float(rows[0]["ragas.faithfulness"]) == 0.75
    assert float(rows[0]["ragas.faithfulness.std"]) == pytest.approx(0.353553, abs=1e-6)


def test_cli_writes_json_and_csv(tmp_path, monkeypatch):
    from chaejeom.cli.main import main
    from chaejeom.config import EvalConfig

    config = tmp_path / "eval.yaml"
    config.write_text("metrics: [ragas.faithfulness]\nconcurrency: 1\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    data.write_text(json.dumps({"query": "질문", "contexts": ["문맥"], "answer": "답변"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: ScriptedLLM([STATEMENTS, _verdicts(1, 1)]))

    assert main(["run", "--config", str(config), "--data", str(data), "--out", str(tmp_path / "out.json")]) == 0
    assert (tmp_path / "out.json").exists()
    assert float(_read(tmp_path / "out.csv")[0]["ragas.faithfulness"]) == 1.0
