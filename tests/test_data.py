import json

import pytest

from chaejeom.data import load_samples


def test_reference_fields_are_ignored_and_unknown_fields_move_to_metadata(tmp_path):
    path = tmp_path / "ragas.jsonl"
    row = {"user_input": "질문", "retrieved_contexts": ["문맥"], "response": "답변", "reference": "정답", "user_id": "u1"}
    path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    notices = []

    sample = load_samples(path, notices)[0]

    assert sample.query == "질문" and sample.metadata == {"user_id": "u1"}
    assert notices == [("reference_fields", "reference"), ("metadata_fields", "user_id")]


def test_jsonl_lines_split_only_on_newlines(tmp_path):
    path = tmp_path / "a.jsonl"
    path.write_text(json.dumps({"query": "질문 계속", "answer": "답\x85변"}, ensure_ascii=False) + "\n", encoding="utf-8")

    assert load_samples(path)[0].query == "질문 계속"


def test_csv_reads_korean_excel_and_bracketed_documents(tmp_path):
    path = tmp_path / "excel.csv"
    path.write_bytes("query,contexts,answer\n수수료는?,[공지] 수수료는 3%입니다.,3%입니다.\n".encode("cp949"))
    notices = []

    sample = load_samples(path, notices)[0]

    assert [c.text for c in sample.contexts] == ["[공지] 수수료는 3%입니다."]
    assert notices == [("cp949", "")]




def test_load_samples_jsonl(tmp_path):
    path = tmp_path / "samples.jsonl"
    rows = [{"query": "질문", "contexts": ["가", "나"], "answer": "답변"}] * 2
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n\n", encoding="utf-8")

    samples = load_samples(path)

    assert len(samples) == 2
    assert samples[0].contexts[1].id == "c2"


def test_load_samples_reports_bad_row(tmp_path):
    path = tmp_path / "samples.jsonl"
    path.write_text('{"query": "질문", "answer": "답"}\n{"query": "질문", "contexts": 3}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="2번째"):
        load_samples(path)
