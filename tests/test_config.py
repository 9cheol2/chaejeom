import os

import pytest

from chaejeom.config import load_config, load_dotenv


def test_load_config_passes_extra_options(tmp_path):
    path = tmp_path / "eval.yaml"
    path.write_text(
        "judge:\n  provider: openai\n  model: gpt-5\n  reasoning_effort: low\n"
        "metrics:\n  ragas: [faithfulness]\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.judge.options == {"reasoning_effort": "low"}
    assert config.metrics == {"ragas": ["faithfulness"]}


def test_config_defaults(tmp_path):
    path = tmp_path / "eval.yaml"
    path.write_text("preset: rag-triad\n", encoding="utf-8")

    config = load_config(path)

    assert (config.judge.provider, config.judge.model) == ("openai", "gpt-4.1-mini")
    assert (config.embedding.provider, config.embedding.model) == ("openai", "text-embedding-3-large")


def test_load_config_rejects_unknown_keys(tmp_path):
    path = tmp_path / "eval.yaml"
    path.write_text("judge: {provider: openai, model: gpt-5}\nmetric: [x]\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(path)


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# 주석\nCHAEJEOM_A='1'\nCHAEJEOM_B=2\n", encoding="utf-8")
    monkeypatch.setenv("CHAEJEOM_B", "기존")
    monkeypatch.delenv("CHAEJEOM_A", raising=False)

    load_dotenv(path)

    import os

    assert os.environ["CHAEJEOM_A"] == "1"
    assert os.environ["CHAEJEOM_B"] == "기존"


def test_config_runs_and_old_name_repeats(tmp_path):
    for key in ("runs", "repeats"):
        path = tmp_path / f"{key}.yaml"
        path.write_text(f"{key}: 3\n", encoding="utf-8")
        assert load_config(path).runs == 3


def test_dotenv_handles_bom_export_and_comments(tmp_path, monkeypatch):
    for key in ("CHAEJEOM_A", "CHAEJEOM_B", "CHAEJEOM_C"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_bytes("﻿CHAEJEOM_A=1\nexport CHAEJEOM_B=2 # 주석\nCHAEJEOM_C='3 # 값'\n".encode("utf-8"))

    load_dotenv(path)

    assert (os.environ["CHAEJEOM_A"], os.environ["CHAEJEOM_B"], os.environ["CHAEJEOM_C"]) == ("1", "2", "3 # 값")
