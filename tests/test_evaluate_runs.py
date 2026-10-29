import asyncio
import json

import openai
import pytest
from fakes import ScriptedLLM

from chaejeom import aevaluate, evaluate
from chaejeom.cache import ResponseCache
from chaejeom.cli.main import main
from chaejeom.config import EvalConfig
from chaejeom.evaluate import select_metrics
from chaejeom.llm.base import LoopBound
from chaejeom.schema import EvalSample

STATEMENTS = json.dumps({"statements": ["진술 1"]}, ensure_ascii=False)


VERDICTS = json.dumps({"statements": [{"statement": "진술 1", "reason": "있음", "verdict": 1}]}, ensure_ascii=False)


SAMPLE = EvalSample(id="a", query="질문", contexts=["문맥"], answer="답변")


def test_presets_split_upstream_and_all():
    assert len(select_metrics(preset="rag-triad")) == 9
    assert not any(m.startswith("chaejeom.") for m in select_metrics(preset="rag-triad"))
    assert len(select_metrics(preset="all")) == 12


async def test_result_records_label_dataset_and_fingerprints(tmp_path):
    from chaejeom.customize.domain import DomainProfile, save_profile
    from chaejeom.customize.prompt_file import PromptFile, save_prompt
    from chaejeom.metrics.chaejeom.prompts import TEMPLATES

    domain = save_profile(DomainProfile(name="인사"), tmp_path / "d.yaml")
    prompt = save_prompt(PromptFile(metric="chaejeom.answer_relevance", requests=["요청"], template=TEMPLATES["chaejeom.answer_relevance"]), tmp_path / "p.yaml")
    response = json.dumps({"evasive": False, "same_target": True, "discusses_asked": True, "answers_directly": True})
    options = {"domain": str(domain), "prompt": str(prompt)}

    result = await aevaluate([SAMPLE], ScriptedLLM([response]), metrics=[{"chaejeom.answer_relevance": options}], label="v1", repeats=1)

    assert result.label == "v1" and len(result.dataset) == 12
    entry = result.fingerprints["chaejeom.answer_relevance"]
    # The custom prompt replaces the domain's prompt, so the domain is not recorded as a judging criterion.
    assert set(entry) == {"prompt", "requests"} and entry["requests"] == ["요청"]
    without_prompt = await aevaluate([SAMPLE], ScriptedLLM([response]), metrics=[{"chaejeom.answer_relevance": {"domain": str(domain)}}], repeats=1)
    assert set(without_prompt.fingerprints["chaejeom.answer_relevance"]) == {"domain"}


async def test_missing_domain_or_prompt_file_fails_before_any_call(tmp_path):
    llm = ScriptedLLM([])
    metrics = [{"chaejeom.answer_relevance": {"domain": str(tmp_path / "gone.yaml")}}, "ragas.faithfulness"]

    with pytest.raises(FileNotFoundError, match="도메인 정보 파일"):
        await aevaluate([SAMPLE], llm, metrics=metrics, repeats=1)
    assert llm.calls == []


async def test_cache_argument_decides_for_each_run(tmp_path):
    llm = ScriptedLLM([STATEMENTS, VERDICTS, STATEMENTS, VERDICTS])
    llm.cache = ResponseCache(tmp_path / "c1")

    await aevaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=1)
    result = await aevaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], cache=False, repeats=1)

    assert result.cost.llm_calls == 2 and result.cost.cache_hits == 0
    assert llm.cache.path.parent == tmp_path / "c1"


async def test_failed_metric_keeps_the_cost_it_spent():
    llm = ScriptedLLM([STATEMENTS, "JSON 아님", "JSON 아님", "JSON 아님"])

    result = await aevaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=1)

    assert result.samples[0].results[0].error
    assert result.cost.llm_calls == 4


async def test_run_statistics_use_only_samples_scored_in_every_run():
    good, flaky = EvalSample(id="good", answer="답변", query="질문"), EvalSample(id="flaky", answer="답변", query="질문")
    direct = json.dumps({"evasive": False, "same_target": True, "discusses_asked": True, "answers_directly": True})
    evasive = json.dumps({"evasive": True, "same_target": True, "discusses_asked": False, "answers_directly": False})
    # Run 1: good scores 1.0 and flaky fails as malformed. Run 2: good scores 1.0 and flaky scores 0.
    llm = ScriptedLLM([direct, "x", "x", "x", direct, evasive])

    result = await aevaluate([good, flaky], llm, metrics=["chaejeom.answer_relevance"], repeats=2, concurrency=1)

    summary = result.summary[0]
    assert (summary.mean, summary.std, summary.dropped) == (1.0, 0.0, 1)


def test_evaluate_works_inside_a_running_event_loop():
    async def notebook_cell():
        return evaluate([SAMPLE], ScriptedLLM([STATEMENTS, VERDICTS]), metrics=["ragas.faithfulness"], repeats=1)

    assert asyncio.run(notebook_cell()).summary[0].mean == 1.0


def test_loop_bound_client_is_rebuilt_for_a_new_event_loop():
    made = []
    clients = LoopBound(lambda: made.append(object()) or made[-1])

    async def get():
        return clients.get()

    first, again = asyncio.run(get()), asyncio.run(get())

    assert first is made[0] and again is made[1] and len(made) == 2


class _DeniedLLM(ScriptedLLM):
    async def _complete(self, messages, system, json_mode):
        # Build the error without its constructor, which needs an SDK-specific HTTP response object.
        error = openai.AuthenticationError.__new__(openai.AuthenticationError)
        Exception.__init__(error, "invalid key")
        raise error


async def test_wrong_api_key_stops_the_run():
    with pytest.raises(openai.AuthenticationError):
        await aevaluate([SAMPLE, SAMPLE], _DeniedLLM([]), metrics=["ragas.faithfulness", "deepeval.faithfulness"], repeats=1)


def _run_cli(tmp_path, monkeypatch, llm, *extra):
    config = tmp_path / "eval.yaml"
    config.write_text("metrics: [ragas.faithfulness]\nconcurrency: 1\nruns: 1\n", encoding="utf-8")
    data = tmp_path / "samples.jsonl"
    rows = [{"id": f"s{i}", "query": "질문", "contexts": ["문맥"], "answer": "답변"} for i in range(3)]
    data.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.setattr(EvalConfig, "create_llm", lambda self: llm)
    return main(["run", "--config", str(config), "--data", str(data), *extra])
