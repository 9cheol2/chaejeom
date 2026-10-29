import csv
from pathlib import Path
from statistics import fmean, stdev
from typing import Any

from pydantic import BaseModel, Field

from chaejeom.metrics import get_metric
from chaejeom.schema import AXIS_LABELS, Cost, MetricResult

SCHEMA_VERSION = 1


class Stat(BaseModel):
    """Per-run values with their mean and sample standard deviation (``None`` with fewer than 2 values)."""

    mean: float | None
    std: float | None
    runs: list[float | None]


def make_stat(runs: list[float | None]) -> Stat:
    values = [v for v in runs if v is not None]
    return Stat(
        mean=fmean(values) if values else None,
        std=stdev(values) if len(values) >= 2 else None,
        runs=runs,
    )


class SampleResult(BaseModel):
    index: int
    id: str
    query: str
    metadata: dict[str, Any]
    scores: dict[str, Stat]
    results: list[MetricResult]


class MetricSummary(Stat):
    """Aggregate statistics for one metric across all samples.

    Per-run stats use only samples scored in every run; otherwise run means would cover
    different samples and show variance even when the judge is perfectly consistent.
    ``dropped`` counts samples excluded for missing a score in some run.
    """

    metric_id: str
    axis: str
    scored: int
    errors: int
    dropped: int = 0


class EvalResult(BaseModel):
    schema_version: int = SCHEMA_VERSION
    chaejeom_version: str
    created_at: str
    label: str | None = None
    judge: dict
    embedding: dict | None
    metrics: dict[str, dict]
    # Fingerprints for checking that two results were measured under the same conditions:
    # `dataset` hashes the samples, `fingerprints` the chaejeom.* domain profiles and custom prompts.
    dataset: str = ""
    fingerprints: dict[str, dict] = Field(default_factory=dict)
    repeats: int
    summary: list[MetricSummary]
    by_axis: dict[str, dict[str, Stat]]
    cost: Cost = Field(default_factory=Cost)
    samples: list[SampleResult]

    def to_csv(self, path: str | Path) -> Path:
        """Write one row per sample to a CSV file (see :func:`write_csv`)."""
        return write_csv(self, path)

    def to_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def in_axis_average(metric_id: str) -> bool:
    """Return whether a metric counts toward its axis average.

    Only upstream framework metrics do; chaejeom.* criteria vary with the domain profile.
    """
    return not metric_id.startswith("chaejeom.")


def write_csv(result: EvalResult, path: str | Path) -> Path:
    """Write one row per sample: metric scores (run mean, plus ``.std`` when repeated), axis averages, and errors.

    Encoded as UTF-8 with BOM so Excel displays Korean correctly.
    """
    path = Path(path)
    metric_ids = [s.metric_id for s in result.summary]
    axes = [a for a in AXIS_LABELS if any(get_metric(m).axis == a for m in metric_ids)]
    meta_keys = sorted({k for s in result.samples for k in s.metadata})
    with_std = result.repeats > 1

    header = ["index", "id", "query", *(f"meta.{k}" for k in meta_keys)]
    for metric_id in metric_ids:
        header.append(metric_id)
        if with_std:
            header.append(f"{metric_id}.std")
    header += [f"axis.{a}" for a in axes]
    header.append("errors")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for sample in result.samples:
            row = [sample.index, sample.id, sample.query, *(sample.metadata.get(k, "") for k in meta_keys)]
            for metric_id in metric_ids:
                stat = sample.scores[metric_id]
                row.append(_cell(stat.mean))
                if with_std:
                    row.append(_cell(stat.std))
            for axis in axes:
                means = [sample.scores[m].mean for m in metric_ids if get_metric(m).axis == axis and in_axis_average(m)]
                means = [v for v in means if v is not None]
                row.append(_cell(fmean(means) if means else None))
            errors = [f"{r.metric_id}#{r.run}: {r.error}" for r in sample.results if r.error]
            row.append(" | ".join(errors))
            writer.writerow(row)
    return path


def _cell(value: float | None) -> str | float:
    return "" if value is None else value
