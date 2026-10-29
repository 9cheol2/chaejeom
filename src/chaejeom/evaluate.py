import asyncio
import hashlib
import json
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

from chaejeom.cache import DEFAULT_CACHE_DIR, ResponseCache, current_run
from chaejeom.defaults import DEFAULT_EMBEDDING, DEFAULT_JUDGE, DEFAULT_RUNS
from chaejeom.embeddings import EmbeddingClient, create_embeddings
from chaejeom.llm import LLMClient, create_llm
from chaejeom.llm.base import task_cost
from chaejeom.metrics import Metric, get_metric, list_metrics, resolve
from chaejeom.results import EvalResult, MetricSummary, SampleResult, Stat, in_axis_average, make_stat
from chaejeom.schema import AXIS_LABELS, Cost, EvalSample, MetricResult

# "rag-triad" selects the 9 upstream framework metrics; "all" adds the chaejeom.* metrics (12 total).
PRESETS: dict[str, list[str]] = {"rag-triad": ["ragas.*", "deepeval.*", "trulens.*"], "all": ["*"]}

# A metric is given either by name or as {name: options}.
MetricEntry = str | dict[str, dict | None]
MetricSelection = dict[str, list[MetricEntry] | str] | list[MetricEntry]


def _axis_key(axis: str) -> str:
    if axis in AXIS_LABELS:
        return axis
    for key, label in AXIS_LABELS.items():
        if axis == label:
            return key
    raise ValueError(f"알 수 없는 축입니다: {axis} (가능한 값: {', '.join(AXIS_LABELS.values())})")


def _split_entry(entry: MetricEntry, prefix: str = "") -> list[tuple[str, dict]]:
    if isinstance(entry, str):
        return [(prefix + entry, {})]
    return [(prefix + name, options or {}) for name, options in entry.items()]


def select_metrics(
    metrics: MetricSelection | None = None,
    axis: str | list[str] | None = None,
    preset: str | None = None,
) -> dict[str, dict]:
    """Resolve a metric selection into ``{metric_id: options}``.

    Metrics picked by name/pattern, axis, and preset are merged; a metric selected
    more than once appears once, with its options combined.

    Raises:
        ValueError: If the axis or preset is unknown, or nothing is selected.
    """
    entries: list[tuple[str, dict]] = []
    if isinstance(metrics, dict):
        for framework, names in metrics.items():
            if names == "all":
                entries.append((f"{framework}.*", {}))
            else:
                for entry in names:
                    entries.extend(_split_entry(entry, prefix=f"{framework}."))
    elif metrics:
        for entry in metrics:
            entries.extend(_split_entry(entry))

    if preset is not None:
        if preset not in PRESETS:
            raise ValueError(f"알 수 없는 프리셋입니다: {preset} (가능한 값: {', '.join(PRESETS)})")
        entries.extend((pattern, {}) for pattern in PRESETS[preset])

    selected: dict[str, dict] = {}
    for pattern, options in entries:
        for metric_id in resolve([pattern]):
            selected.setdefault(metric_id, {}).update(options)

    if axis is not None:
        axes = {_axis_key(a) for a in ([axis] if isinstance(axis, str) else axis)}
        for metric_id in list_metrics():
            if get_metric(metric_id).axis in axes:
                selected.setdefault(metric_id, {})

    if not selected:
        raise ValueError("평가할 지표를 하나 이상 고르세요.")
    return selected


def needs_embeddings(metric_ids: Iterable[str]) -> bool:
    return any("embeddings" in get_metric(m).requires for m in metric_ids)


def _client_info(client: LLMClient | EmbeddingClient | None) -> dict | None:
    if client is None:
        return None
    info = {"client": type(client).__name__, "model": client.model}
    for attr in ("temperature", "reasoning_effort"):
        if getattr(client, attr, None) is not None:
            info[attr] = getattr(client, attr)
    return info


async def _measure(metric: Metric, sample: EvalSample) -> MetricResult:
    missing = metric.missing_fields(sample)
    if missing:
        return metric.result(error=f"이 지표에 필요한 입력이 비어 있습니다: {', '.join(missing)}")
    spent = Cost()
    task_cost.set(spent)
    try:
        return await metric.ameasure(sample)
    except Exception as e:
        if _fatal(e):
            raise
        # Keep the cost of calls made before the failure.
        return metric.result(error=f"{type(e).__name__}: {e}", cost=spent)
    finally:
        task_cost.set(None)


def _fatal(error: Exception) -> bool:
    """Return True for errors (bad API key, no permission, unknown model) that would fail every sample alike."""
    import openai

    return isinstance(error, (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError))


def _mean_or_none(values: list[float | None]) -> float | None:
    values = [v for v in values if v is not None]
    return fmean(values) if values else None


def _summarize(metric_ids: list[str], samples: list[SampleResult], repeats: int) -> list[MetricSummary]:
    """Average samples per run, then take the mean and std of those per-run means.

    Only samples scored in every run are used, so each run mean covers the same samples.
    """
    summary = []
    for metric_id in metric_ids:
        mine = [r for s in samples for r in s.results if r.metric_id == metric_id]
        scored = [s.scores[metric_id].runs for s in samples if any(v is not None for v in s.scores[metric_id].runs)]
        complete = [runs for runs in scored if all(v is not None for v in runs)]
        run_means = [_mean_or_none([runs[run] for runs in complete]) for run in range(repeats)]
        summary.append(
            MetricSummary(
                metric_id=metric_id,
                axis=get_metric(metric_id).axis,
                scored=sum(1 for r in mine if r.score is not None),
                errors=sum(1 for r in mine if r.error),
                dropped=len(scored) - len(complete),
                **make_stat(run_means).model_dump(),
            )
        )
    return summary


def _by_axis(summary: list[MetricSummary], repeats: int) -> dict[str, dict[str, Stat]]:
    """Build ``{axis: {framework: Stat, "average": Stat}}``.

    The axis average is computed per run over the upstream metrics on that axis only.
    """
    table: dict[str, dict[str, Stat]] = {}
    for axis in AXIS_LABELS:
        items = [s for s in summary if s.axis == axis]
        if not items:
            continue
        row = {item.metric_id.split(".", 1)[0]: Stat(mean=item.mean, std=item.std, runs=item.runs) for item in items}
        upstream = [item for item in items if in_axis_average(item.metric_id)]
        if upstream:
            row["average"] = make_stat([_mean_or_none([item.runs[run] for item in upstream]) for run in range(repeats)])
        table[axis] = row
    return table


def _total_cost(results: list[MetricResult]) -> Cost:
    total = Cost()
    for result in results:
        for field in Cost.model_fields:
            setattr(total, field, getattr(total, field) + getattr(result.cost, field))
    return total


def _sample_scores(metric_ids: list[str], results: list[MetricResult], repeats: int) -> dict[str, Stat]:
    by_run = {(r.metric_id, r.run): r.score for r in results}
    return {m: make_stat([by_run.get((m, run)) for run in range(1, repeats + 1)]) for m in metric_ids}


async def aevaluate(
    samples: list[EvalSample],
    llm: LLMClient | None = None,
    metrics: MetricSelection | None = None,
    axis: str | list[str] | None = None,
    preset: str | None = None,
    embeddings: EmbeddingClient | None = None,
    concurrency: int = 4,
    repeats: int = DEFAULT_RUNS,
    cache: bool | str = True,
    on_progress: Callable[[int, int], None] | None = None,
    label: str | None = None,
) -> EvalResult:
    """Evaluate samples with the selected metrics.

    Args:
        samples: Samples to evaluate.
        llm: Judge model. Defaults to ``DEFAULT_JUDGE``.
        metrics: Metric names/patterns, either a flat list or ``{framework: [names] | "all"}``.
            Entries may be ``{name: options}``.
        axis: Select every metric on these axes (key or Korean label).
        preset: Named selection from ``PRESETS``.
        embeddings: Embedding client. Created from ``DEFAULT_EMBEDDING`` only if a metric needs it.
        concurrency: Maximum number of metric evaluations in flight.
        repeats: Number of runs. Each run is judged independently (separate cache entries),
            and results report the per-run scores with their mean and std.
        cache: ``True`` caches LLM responses in ``.chaejeom_cache/``, a string uses that directory,
            ``False`` disables caching for this call. The caller's ``llm.cache`` is restored afterwards.
        on_progress: Called with ``(done, total)`` after each metric evaluation.
        label: Run name stored in the result.

    Raises:
        ValueError: If ``repeats < 1`` or the metric selection is invalid.
    """
    if repeats < 1:
        raise ValueError("repeats 는 1 이상이어야 합니다.")
    selected = select_metrics(metrics, axis, preset)
    if llm is None:
        llm = create_llm(**DEFAULT_JUDGE)
    previous_cache, opened = llm.cache, None
    if cache is False:
        llm.cache = None
    elif cache is not True and (previous_cache is None or previous_cache.path.parent != Path(cache)):
        llm.cache = opened = ResponseCache(cache)
    elif previous_cache is None:
        llm.cache = opened = ResponseCache(DEFAULT_CACHE_DIR)
    try:
        return await _evaluate(samples, llm, selected, embeddings, concurrency, repeats, on_progress, label)
    finally:
        llm.cache = previous_cache
        if opened is not None:
            opened.close()


async def _evaluate(
    samples: list[EvalSample],
    llm: LLMClient,
    selected: dict[str, dict],
    embeddings: EmbeddingClient | None,
    concurrency: int,
    repeats: int,
    on_progress: Callable[[int, int], None] | None,
    label: str | None,
) -> EvalResult:
    from chaejeom import __version__

    if embeddings is None and needs_embeddings(selected):
        embeddings = create_embeddings(**DEFAULT_EMBEDDING)
    # Instantiate up front so option errors (e.g. typos) fail before any API call.
    instances = [get_metric(m)(llm=llm, embeddings=embeddings, options=o) for m, o in selected.items()]
    _check_prompt_files(instances)

    semaphore = asyncio.Semaphore(concurrency)
    total = repeats * len(samples) * len(instances)
    done = 0

    async def run(metric: Metric, sample: EvalSample, run_no: int) -> MetricResult:
        nonlocal done
        current_run.set(run_no)
        async with semaphore:
            result = await _measure(metric, sample)
        done += 1
        if on_progress:
            on_progress(done, total)
        return result.model_copy(update={"run": run_no})

    # per_run[run][sample][metric]
    per_run = await asyncio.gather(
        *(
            asyncio.gather(*(asyncio.gather(*(run(m, s, run_no) for m in instances)) for s in samples))
            for run_no in range(1, repeats + 1)
        )
    )
    metric_ids = list(selected)
    sample_results = []
    for i, sample in enumerate(samples):
        results = [r for run_results in per_run for r in run_results[i]]
        sample_results.append(
            SampleResult(
                index=i,
                id=sample.id if sample.id is not None else str(i),
                query=sample.query,
                metadata=sample.metadata,
                scores=_sample_scores(metric_ids, results, repeats),
                results=results,
            )
        )
    all_results = [r for s in sample_results for r in s.results]
    summary = _summarize(metric_ids, sample_results, repeats)

    return EvalResult(
        chaejeom_version=__version__,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        label=label,
        judge=_client_info(llm),
        embedding=_client_info(embeddings),
        metrics={m.metric_id: m.options.model_dump() for m in instances},
        dataset=dataset_fingerprint(samples),
        fingerprints=_fingerprints(instances),
        repeats=repeats,
        summary=summary,
        by_axis=_by_axis(summary, repeats),
        cost=_total_cost(all_results),
        samples=sample_results,
    )


def dataset_fingerprint(samples: list[EvalSample]) -> str:
    """Return a short hash of the samples, used to tell whether two results share a dataset."""
    data = json.dumps([s.model_dump(mode="json") for s in samples], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


def _check_prompt_files(instances: list[Metric]) -> None:
    """Read every domain profile and custom prompt file once, so a missing or broken file fails before any API call."""
    from chaejeom.metrics.chaejeom.judging import DomainOptions, template_for

    for metric in instances:
        if isinstance(metric.options, DomainOptions):
            template_for(metric.options, metric.metric_id)


def _fingerprints(instances: list[Metric]) -> dict[str, dict]:
    """Fingerprint each metric's domain profile and custom prompt.

    The file paths in the options alone cannot reveal that a file's content changed. A custom prompt
    replaces the domain's prompt entirely, so the domain is recorded only when no custom prompt is set.
    """
    from chaejeom.customize.domain import load_profile
    from chaejeom.customize.prompt_file import load_prompt

    out: dict[str, dict] = {}
    for metric in instances:
        options = metric.options.model_dump()
        entry: dict = {}
        # The files were read before the run started; one removed meanwhile just loses its fingerprint.
        try:
            if options.get("domain") and not options.get("prompt"):
                entry["domain"] = load_profile(options["domain"]).fingerprint()
            if options.get("prompt"):
                prompt = load_prompt(options["prompt"], metric.metric_id)
                entry["prompt"] = hashlib.sha256(prompt.template.encode("utf-8")).hexdigest()[:12]
                entry["requests"] = prompt.requests
        except (OSError, ValueError):
            pass
        if entry:
            out[metric.metric_id] = entry
    return out


def evaluate(samples: list[EvalSample], llm: LLMClient | None = None, **kwargs) -> EvalResult:
    """Synchronous wrapper around :func:`aevaluate`.

    If an event loop is already running (e.g. Jupyter), the evaluation runs in a worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(aevaluate(samples, llm, **kwargs))
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, aevaluate(samples, llm, **kwargs)).result()
