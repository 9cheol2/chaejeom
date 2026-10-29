import json

import pytest
from fakes import ScriptedLLM

from chaejeom import aevaluate
from chaejeom.evaluate import select_metrics
from chaejeom.schema import EvalSample

STATEMENTS = json.dumps({"statements": ["진술 1", "진술 2"]}, ensure_ascii=False)


VERDICTS = json.dumps(
    {
        "statements": [
            {"statement": "진술 1", "reason": "있음", "verdict": 1},
            {"statement": "진술 2", "reason": "없음", "verdict": 0},
        ]
    },
    ensure_ascii=False,
)


def _sample(contexts=("문맥",)):
    return EvalSample(query="질문", contexts=list(contexts), answer="답변")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metrics": {"ragas": ["faithfulness"]}},
        {"metrics": {"ragas": "all"}},
        {"metrics": ["ragas.*", "ragas.faithfulness"]},
        {"axis": "근거성"},
        {"axis": "groundedness"},
        {"preset": "rag-triad"},
    ],
)
def test_select_metrics(kwargs):
    assert "ragas.faithfulness" in select_metrics(**kwargs)


def test_select_metrics_with_options():
    selected = select_metrics({"ragas": [{"faithfulness": {"x": 1}}]}, axis="근거성")

    assert selected["ragas.faithfulness"] == {"x": 1}


def test_select_metrics_errors():
    with pytest.raises(ValueError, match="하나 이상"):
        select_metrics()
    with pytest.raises(ValueError, match="축"):
        select_metrics(axis="완결성")
    with pytest.raises(ValueError, match="프리셋"):
        select_metrics(preset="everything")


async def test_errors_are_recorded_and_others_continue():
    llm = ScriptedLLM([STATEMENTS, VERDICTS])
    progress = []

    result = await aevaluate(
        [_sample(contexts=[]), _sample()],
        llm,
        metrics=["ragas.faithfulness"],
        concurrency=1,
        repeats=1,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    first, second = (s.results[0] for s in result.samples)
    assert first.score is None and "contexts" in first.error
    assert second.score == 0.5 and second.error is None
    assert result.summary[0].mean == 0.5
    assert result.summary[0].scored == 1
    assert result.summary[0].errors == 1
    assert result.judge["model"] == "scripted"
    assert progress[-1] == (2, 2)


async def test_result_keeps_sample_id_metadata_and_axis_table():
    llm = ScriptedLLM([STATEMENTS, VERDICTS])
    sample = EvalSample(id="hr-001", query="질문", contexts=["문맥"], answer="답변", metadata={"model": "A"})

    result = await aevaluate([sample], llm, metrics=["ragas.faithfulness"], repeats=1)

    assert result.schema_version == 1
    assert result.samples[0].id == "hr-001"
    assert result.samples[0].metadata == {"model": "A"}
    assert result.by_axis["groundedness"]["ragas"].mean == 0.5
    assert result.by_axis["groundedness"]["average"].mean == 0.5
    assert result.by_axis["groundedness"]["ragas"].std is None
    assert result.metrics == {"ragas.faithfulness": {}}
    assert result.repeats == 1


VERDICTS_ALL_YES = json.dumps(
    {
        "statements": [
            {"statement": "진술 1", "reason": "있음", "verdict": 1},
            {"statement": "진술 2", "reason": "있음", "verdict": 1},
        ]
    },
    ensure_ascii=False,
)


async def test_repeats_give_mean_and_std():
    llm = ScriptedLLM([STATEMENTS, VERDICTS, STATEMENTS, VERDICTS_ALL_YES])

    result = await aevaluate([_sample()], llm, metrics=["ragas.faithfulness"], repeats=2, concurrency=1)

    summary = result.summary[0]
    assert summary.runs == [0.5, 1.0]
    assert summary.mean == 0.75
    assert summary.std == pytest.approx(0.353553, abs=1e-6)
    assert [r.run for r in result.samples[0].results] == [1, 2]
    assert result.samples[0].scores["ragas.faithfulness"].runs == [0.5, 1.0]
    assert summary.scored == 2


def test_axis_average_per_run(monkeypatch):
    from chaejeom.metrics import base
    from chaejeom.schema import Source

    def fake(metric_id: str, framework: str, scores: list[float]):
        class Fake(base.Metric):
            async def ameasure(self, sample):
                return self.result(score=scores.pop(0))

        Fake.metric_id = metric_id
        Fake.axis = "groundedness"
        Fake.source = Source(framework=framework, version="t", commit="t", method="t")
        return Fake

    monkeypatch.setattr(base, "_REGISTRY", {})
    base.register(fake("ragas.faithfulness", "ragas", [0.2, 0.4]))
    base.register(fake("trulens.groundedness", "trulens", [0.6, 1.0]))

    from chaejeom import evaluate

    result = evaluate([EvalSample()], ScriptedLLM([]), axis="근거성", repeats=2, concurrency=1)

    average = result.by_axis["groundedness"]["average"]
    assert average.runs == pytest.approx([0.4, 0.7])
    assert average.mean == pytest.approx(0.55)
    assert average.std == pytest.approx(0.212132, abs=1e-6)


def test_repeats_must_be_positive():
    with pytest.raises(ValueError, match="repeats"):
        from chaejeom import evaluate

        evaluate([_sample()], ScriptedLLM([]), metrics=["ragas.faithfulness"], repeats=0)


def test_cost_tracks_input_output_tokens_and_estimated_usd():
    from chaejeom.pricing import REFERENCE, SampleStats, estimate_usd, usd

    assert usd("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert usd("unknown-model", 10, 10) is None
    reference = SampleStats(*REFERENCE)
    single = estimate_usd(["chaejeom.answer_relevance"], reference, 1, 1, "gpt-4o-mini")
    assert single == pytest.approx((798 * 0.15 + 86 * 0.60) / 1_000_000)
    assert estimate_usd(["chaejeom.answer_relevance"], reference, 10, 3, "gpt-4o-mini") == pytest.approx(single * 30)
    assert estimate_usd(["chaejeom.answer_relevance"], reference._replace(chars=266), 1, 1, "gpt-4o-mini") > single
    assert estimate_usd(["chaejeom.answer_relevance"], reference, 1, 1, "unknown-model") is None
    # Per-chunk metrics scale linearly with the number of context chunks.
    per_chunk = estimate_usd(["trulens.context_relevance"], reference, 1, 1, "gpt-4o-mini")
    assert estimate_usd(["trulens.context_relevance"], reference._replace(chunks=REFERENCE[1] * 3), 1, 1, "gpt-4o-mini") == pytest.approx(per_chunk * 3)
