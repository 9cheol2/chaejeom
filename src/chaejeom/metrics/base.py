from abc import ABC, abstractmethod
from fnmatch import fnmatchcase
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from chaejeom.embeddings.base import EmbeddingClient
from chaejeom.llm.base import LLMClient
from chaejeom.schema import Axis, EvalSample, MetricResult, Source

Requirement = Literal["query", "answer", "contexts", "embeddings"]
SAMPLE_FIELDS: tuple[Requirement, ...] = ("query", "answer", "contexts")


class MetricOptions(BaseModel):
    """Base class for per-metric options.

    Each metric subclasses this to declare its upstream parameters and defaults.
    Unknown options are rejected.
    """

    model_config = ConfigDict(extra="forbid")


class Metric(ABC):
    """Base class for an LLM-as-a-judge metric.

    Raises:
        ValueError: If the metric needs embeddings and none are given, or if
            `options` does not validate against `Options`.
    """

    metric_id: ClassVar[str]
    axis: ClassVar[Axis]
    source: ClassVar[Source]
    requires: ClassVar[frozenset[Requirement]] = frozenset()
    Options: ClassVar[type[MetricOptions]] = MetricOptions

    def __init__(
        self,
        llm: LLMClient,
        embeddings: EmbeddingClient | None = None,
        options: dict | None = None,
    ):
        if "embeddings" in self.requires and embeddings is None:
            raise ValueError(f"{self.metric_id} 지표는 임베딩 설정이 필요합니다.")
        self.llm = llm
        self.embeddings = embeddings
        try:
            self.options = self.Options(**(options or {}))
        except ValueError as e:
            raise ValueError(f"{self.metric_id} 지표 옵션이 잘못되었습니다.\n{e}") from None

    def missing_fields(self, sample: EvalSample) -> list[str]:
        """Return the required sample fields that are empty."""
        return [f for f in SAMPLE_FIELDS if f in self.requires and not getattr(sample, f)]

    @abstractmethod
    async def ameasure(self, sample: EvalSample) -> MetricResult: ...

    def result(self, **fields) -> MetricResult:
        """Build a `MetricResult` stamped with this metric's id, source and axis."""
        return MetricResult(metric_id=self.metric_id, source=self.source, axis=self.axis, **fields)


_REGISTRY: dict[str, type[Metric]] = {}


def register(cls: type[Metric]) -> type[Metric]:
    """Class decorator that adds a metric to the registry under its `metric_id`."""
    if cls.metric_id in _REGISTRY:
        raise ValueError(f"이미 등록된 지표입니다: {cls.metric_id}")
    _REGISTRY[cls.metric_id] = cls
    return cls


def get_metric(metric_id: str) -> type[Metric]:
    """Return the registered metric class for `metric_id`."""
    try:
        return _REGISTRY[metric_id]
    except KeyError:
        raise KeyError(f"등록되지 않은 지표입니다: {metric_id}") from None


def list_metrics() -> list[str]:
    """Return all registered metric ids, sorted."""
    return sorted(_REGISTRY)


def resolve(patterns: list[str]) -> list[str]:
    """Expand metric ids or glob patterns such as `ragas.*` into metric ids.

    Ids keep their match order, and an id matched more than once appears once.

    Raises:
        KeyError: If a pattern matches no registered metric.
    """
    resolved: list[str] = []
    for pattern in patterns:
        matched = [m for m in list_metrics() if fnmatchcase(m, pattern)]
        if not matched:
            raise KeyError(f"일치하는 지표가 없습니다: {pattern}")
        resolved.extend(m for m in matched if m not in resolved)
    return resolved
