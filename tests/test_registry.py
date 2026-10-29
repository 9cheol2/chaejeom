import pytest

from chaejeom.metrics import base
from chaejeom.schema import EvalSample, MetricResult, Source


def _fake_metric(metric_id: str, requires=frozenset()):
    class Fake(base.Metric):
        async def ameasure(self, sample: EvalSample) -> MetricResult:
            raise NotImplementedError

    Fake.metric_id = metric_id
    Fake.axis = "groundedness"
    Fake.source = Source(framework="ragas", version="v0.4.3", commit="test", method="test")
    Fake.requires = requires
    return Fake


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch):
    monkeypatch.setattr(base, "_REGISTRY", {})


def test_resolve_wildcard_and_dedup():
    for metric_id in ["ragas.faithfulness", "ragas.context_relevance", "trulens.groundedness"]:
        base.register(_fake_metric(metric_id))

    assert base.resolve(["ragas.*", "ragas.faithfulness"]) == [
        "ragas.context_relevance",
        "ragas.faithfulness",
    ]


def test_resolve_unknown_raises():
    with pytest.raises(KeyError):
        base.resolve(["deepeval.*"])


def test_duplicate_register_raises():
    base.register(_fake_metric("ragas.faithfulness"))
    with pytest.raises(ValueError):
        base.register(_fake_metric("ragas.faithfulness"))


class _StrictnessOptions(base.MetricOptions):
    strictness: int = 3


def test_options_defaults_and_overrides():
    metric_cls = _fake_metric("ragas.response_relevancy")
    metric_cls.Options = _StrictnessOptions

    assert metric_cls(llm=object()).options.strictness == 3
    assert metric_cls(llm=object(), options={"strictness": 5}).options.strictness == 5
    with pytest.raises(ValueError, match="옵션"):
        metric_cls(llm=object(), options={"strictnes": 5})


def test_missing_fields():
    metric_cls = _fake_metric("trulens.groundedness", requires=frozenset({"answer", "contexts"}))
    metric = metric_cls(llm=object())

    assert metric.missing_fields(EvalSample(answer="답변")) == ["contexts"]
    assert metric.missing_fields(EvalSample(answer="답변", contexts=["문맥"])) == []


def test_embeddings_required():
    metric_cls = _fake_metric("ragas.response_relevancy", requires=frozenset({"embeddings"}))
    with pytest.raises(ValueError, match="임베딩"):
        metric_cls(llm=object())
