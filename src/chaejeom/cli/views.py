"""Rich views for result tables and per-sample judgments, shared by ``chaejeom run`` and interactive mode."""

import re
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from chaejeom.cli import banner
from chaejeom.cli.i18n import t
from chaejeom.metrics import get_metric, list_metrics
from chaejeom.pricing import PRICES, PRICES_AS_OF
from chaejeom.results import EvalResult, SampleResult, Stat, in_axis_average
from chaejeom.schema import MetricResult, Unit

# Ordered by popularity, with Chaejeom's own metrics last.
FRAMEWORKS = ("ragas", "deepeval", "trulens", "chaejeom")
FRAMEWORK_LABELS = {"ragas": "RAGAS", "deepeval": "DeepEval", "trulens": "TruLens", "chaejeom": "Chaejeom"}
AXES = ("groundedness", "context_relevance", "answer_relevance")
# Names that appear as keys in config and result files (axes, config labels, table headers) stay in English
# regardless of the UI language.
AXIS_NAMES = {"groundedness": "Groundedness", "context_relevance": "Context relevance", "answer_relevance": "Answer relevance"}

# Metric names as each framework calls them.
METRIC_NAMES = {
    "ragas.faithfulness": "Faithfulness",
    "ragas.context_relevance": "ContextRelevance",
    "ragas.response_relevancy": "ResponseRelevancy",
    "deepeval.faithfulness": "Faithfulness",
    "deepeval.contextual_relevancy": "ContextualRelevancy",
    "deepeval.answer_relevancy": "AnswerRelevancy",
    "trulens.groundedness": "Groundedness",
    "trulens.context_relevance": "Context Relevance",
    "trulens.answer_relevance": "Answer Relevance",
    "chaejeom.groundedness": "Groundedness",
    "chaejeom.context_relevance": "Context Relevance",
    "chaejeom.answer_relevance": "Answer Relevance",
}

# Chaejeom judge verdicts, grouped into pass, partial and fail for display.
PASS_VERDICTS = {"supported", "relevant", "direct"}
PARTIAL_VERDICTS = {"unsupported", "partial", "indirect", "other_aspect", "declined"}
FAIL_VERDICTS = {"contradicted", "irrelevant", "off_topic", "evasive"}

GOOD = "#5BC77E"
BAD = banner.RED_PEN
UNSURE = "#FFC145"


def axis_name(axis: str) -> str:
    return AXIS_NAMES[axis]


def column_label(column: str) -> str:
    return "Average" if column == "average" else FRAMEWORK_LABELS[column]


def metrics_grid(metric_ids) -> list[tuple[str, list[bool]]]:
    """Return, per axis, whether each framework (in `FRAMEWORKS` order) is selected. Used by the status footer."""
    by_cell = {(get_metric(m).axis, m.split(".", 1)[0]) for m in metric_ids}
    return [(axis_name(axis), [(axis, f) in by_cell for f in FRAMEWORKS]) for axis in AXES]


def fmt(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def fmt_stat(stat: Stat | None) -> str:
    """Format a stat as the mean, or as "mean ± std" when there were several runs."""
    if stat is None:
        return "-"
    if stat.std is None:
        return fmt(stat.mean)
    return f"{fmt(stat.mean)} ± {stat.std:.2f}"


def ordered_metrics() -> list[str]:
    """Return all metric ids ordered by axis, then by framework."""
    return [
        m
        for axis in AXES
        for framework in FRAMEWORKS
        for m in list_metrics()
        if get_metric(m).axis == axis and m.startswith(framework + ".")
    ]


def path_link(path: str | Path) -> Text:
    """Render a path as a clickable file link. Terminals without hyperlink support show plain text."""
    uri = Path(path).expanduser().resolve().as_uri()
    return Text(str(path), style=f"{banner.PATH} link {uri}")


def metric_label(metric_id: str) -> str:
    framework = metric_id.split(".", 1)[0]
    return f"{FRAMEWORK_LABELS[framework]} {METRIC_NAMES[metric_id]}"


SUMMARY_LINES = 8
FOLD_CHARS = 300
_SLOT = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")


def prompt_text(text: str, full: bool) -> str:
    """Format a prompt for display.

    The summary shows the first few non-empty lines and the input slots; the full view only folds very long lines
    such as an inline JSON Schema.
    """
    lines = [line if len(line) <= FOLD_CHARS else line[:120] + " " + t("prompt.folded", n=len(line)) for line in text.splitlines()]
    if full:
        return "\n".join(lines)
    shown = [line for line in lines if line.strip()][:SUMMARY_LINES]
    rest = len([line for line in lines if line.strip()]) - len(shown)
    slots = ", ".join(dict.fromkeys(f"{{{name}}}" for name in _SLOT.findall(text)))
    footer = [t("prompt.summary_more", n=rest)] if rest > 0 else []
    if slots:
        footer.append(t("prompt.slots", slots=slots))
    return "\n".join([*shown, "", *footer]) if footer else "\n".join(shown)


def print_prompt(console: Console, title: str, text: str) -> None:
    """Print one prompt step in a rounded panel. Passed as `Text` so ``[...]`` in the prompt is not read as markup."""
    console.print(Panel(Text(text, style=banner.TEXT), title=Text(title, style=banner.LABEL), title_align="left", box=box.ROUNDED, border_style=banner.BORDER))


def cost_line(model: str, usd: float) -> str:
    if model not in PRICES:
        return t("cost.unknown", model=model)
    return t("cost.actual", usd=format_usd(usd), model=model, date=PRICES_AS_OF)


def format_usd(usd: float) -> str:
    return f"${usd:.4f}" if usd < 1 else f"${usd:,.2f}"


def print_summary(console: Console, result: EvalResult) -> None:
    """Print the axis × framework score table, the per-metric table and the cost lines."""
    repeated = result.repeats > 1
    title = t("results.title_runs", n=result.repeats) if repeated else t("results.title")
    console.print()
    console.print(Text(title, style="bold"))

    frameworks = [f for f in FRAMEWORKS if any(f in row for row in result.by_axis.values())]
    # Axis averages cover only the original framework metrics, so the column is absent when only Chaejeom metrics ran.
    columns = [*frameworks, *(["average"] if any("average" in row for row in result.by_axis.values()) else [])]
    custom = custom_prompt_metrics(result)
    table = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    table.add_column("")
    for column in columns:
        marked = column == "chaejeom" and bool(custom)
        table.add_column(column_label(column) + ("*" if marked else ""), justify="right")
    for axis in AXES:
        if axis in result.by_axis:
            row = result.by_axis[axis]
            table.add_row(axis_name(axis), *(fmt_stat(row.get(c)) for c in columns))
    console.print(table)

    detail = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    detail.add_column("Metric")
    detail.add_column("Score", justify="right")
    if repeated:
        detail.add_column("Runs", style=banner.MUTED)
    detail.add_column("Scored", justify="right")
    detail.add_column("Errors", justify="right")
    for item in result.summary:
        cells = [item.metric_id + ("*" if item.metric_id in custom else ""), fmt_stat(item)]
        if repeated:
            cells.append(", ".join(fmt(v) for v in item.runs))
        scored = sum(1 for s in result.samples if s.scores[item.metric_id].mean is not None)
        errors = Text(str(item.errors), style=BAD if item.errors else "")
        detail.add_row(*cells, f"{scored}/{len(result.samples)}", errors)
    console.print(detail)
    print_unscored(console, result)
    if custom:
        console.print(Text(t("results.custom_prompt", metrics=", ".join(custom)), style=banner.MUTED))
    if dropped := [item.metric_id for item in result.summary if item.dropped]:
        console.print(Text(t("results.dropped", metrics=", ".join(dropped)), style=banner.MUTED))

    cost = result.cost
    tokens = f"{cost.tokens:,} (in {cost.input_tokens:,} / out {cost.output_tokens:,})"
    console.print(Text(t("results.cost", calls=cost.llm_calls, tokens=tokens, hits=cost.cache_hits), style=banner.MUTED))
    console.print(Text(cost_line(result.judge.get("model", ""), cost.usd), style=banner.MUTED))


UNSCORED_ROWS = 20


def unscored(result: EvalResult) -> list[tuple[str, SampleResult, int, int, str, bool]]:
    """Return ``(metric_id, sample, missing runs, runs, reason, is_error)`` for each sample a metric left unscored in some run."""
    rows = []
    for item in result.summary:
        for sample in result.samples:
            runs = [r for r in sample.results if r.metric_id == item.metric_id]
            missing = [r for r in runs if r.score is None]
            if missing:
                error = next((r.error for r in missing if r.error), None)
                reason = (error or next((r.reason for r in missing if r.reason), "")).strip() or t("results.unscored_no_reason")
                rows.append((item.metric_id, sample, len(missing), len(runs), reason.splitlines()[0], error is not None))
    return rows


def print_unscored(console: Console, result: EvalResult) -> None:
    """List samples without a score and why: by design (e.g. no factual statement) or an error (in red)."""
    rows = unscored(result)
    if not rows:
        return
    console.print(Text(t("results.unscored_title"), style="bold"))
    table = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    for column in ("Metric", "Sample", "Runs", "Reason"):
        table.add_column(column)
    for metric_id, sample, missing, runs, reason, is_error in rows[:UNSCORED_ROWS]:
        table.add_row(metric_id, sample.id, f"{missing}/{runs}", Text(reason, style=BAD if is_error else banner.MUTED))
    console.print(table)
    if len(rows) > UNSCORED_ROWS:
        console.print(Text(t("results.unscored_more", n=len(rows) - UNSCORED_ROWS), style=banner.MUTED))


def custom_prompt_metrics(result: EvalResult) -> list[str]:
    """Return the Chaejeom metrics that were measured with a custom prompt."""
    return [metric_id for metric_id, entry in result.fingerprints.items() if "prompt" in entry]


def all_failed(result: EvalResult) -> str | None:
    """Return the first error message if no metric produced a score, else None.

    This almost always means a wrong API key or model name.
    """
    if any(item.scored for item in result.summary) or not any(item.errors for item in result.summary):
        return None
    return next(r.error for s in result.samples for r in s.results if r.error)


def short_error(error: Exception) -> str:
    """Return a one-line error message for users: the first pydantic error, or the first line of anything else."""
    if hasattr(error, "errors") and callable(error.errors):
        first = error.errors()[0]
        where = ".".join(str(part) for part in first.get("loc", ()))
        return f"{where}: {first.get('msg', '')}" if where else str(first.get("msg", ""))
    if isinstance(error, FileNotFoundError) and error.filename:
        return t("data.not_found", path=error.filename)
    if isinstance(error, KeyError):
        return str(error).strip("'\"")
    return str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__


def endpoint(model) -> str:
    """Return where text is sent: the ``base_url`` if set, otherwise the provider name."""
    return str(model.options.get("base_url") or model.provider)


def data_flow_warnings(config, selected: dict) -> list[str]:
    """Warn when text is sent somewhere other than the judge endpoint.

    Catches setups where the judge is self-hosted but embeddings still go to an external provider.
    """
    from chaejeom.evaluate import needs_embeddings

    judge = endpoint(config.judge)
    if needs_embeddings(selected) and endpoint(config.embedding) != judge:
        return [t("dataflow.embedding", provider=endpoint(config.embedding), model=config.embedding.model, judge=judge)]
    return []


def _delta(before: float | None, after: float | None) -> Text:
    if before is None or after is None:
        return Text("-", style=banner.MUTED)
    diff = after - before
    style = GOOD if diff > 0.005 else BAD if diff < -0.005 else banner.MUTED
    return Text(f"{diff:+.2f}", style=style)


def compare_warnings(before: EvalResult, after: EvalResult) -> list[str]:
    """List the measurement conditions that differ between two results."""
    warnings = []
    if before.dataset and after.dataset and before.dataset != after.dataset:
        warnings.append(t("compare.diff_dataset"))
    for key in ("judge", "embedding"):
        if getattr(before, key) != getattr(after, key):
            warnings.append(t("compare.diff_model", what=key, before=getattr(before, key), after=getattr(after, key)))
    for metric_id in sorted(set(before.fingerprints) | set(after.fingerprints)):
        if before.fingerprints.get(metric_id, {}) != after.fingerprints.get(metric_id, {}):
            warnings.append(t("compare.diff_fingerprint", metric=metric_id))
    if before.repeats != after.repeats:
        warnings.append(t("compare.diff_runs", before=before.repeats, after=after.repeats))
    only = sorted(set(before.metrics) ^ set(after.metrics))
    if only:
        warnings.append(t("compare.diff_metrics", metrics=", ".join(only)))
    return warnings


def _axis_metrics(result: EvalResult, axis: str) -> set[str]:
    """Return the metrics that count towards the axis average."""
    return {s.metric_id for s in result.summary if s.axis == axis and in_axis_average(s.metric_id)}


def print_compare(console: Console, before: EvalResult, after: EvalResult, before_name: str, after_name: str, top: int = 10) -> None:
    """Print axis × framework score deltas between two results, then the samples whose scores changed most."""
    console.print()
    console.print(Text.assemble((t("compare.title") + " ", "bold"), (before_name, banner.PATH), (" → ", banner.MUTED), (after_name, banner.PATH)))
    for warning in compare_warnings(before, after):
        console.print(Text(f"! {warning}", style=UNSURE))

    table = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    table.add_column("")
    columns = [f for f in (*FRAMEWORKS, "average") if any(f in row for rows in (before.by_axis, after.by_axis) for row in rows.values())]
    for column in columns:
        table.add_column(column_label(column), justify="right")
    for axis in AXES:
        if axis not in before.by_axis and axis not in after.by_axis:
            continue
        # Only show an axis-average delta when both results averaged the same metrics; otherwise it would compare
        # averages of different things.
        same_metrics = _axis_metrics(before, axis) == _axis_metrics(after, axis)
        cells = []
        for column in columns:
            a, b = before.by_axis.get(axis, {}).get(column), after.by_axis.get(axis, {}).get(column)
            a_mean, b_mean = (a.mean if a else None), (b.mean if b else None)
            delta = _delta(a_mean, b_mean) if column != "average" or same_metrics else _delta(None, None)
            cells.append(Text.assemble((f"{fmt(a_mean)} → {fmt(b_mean)} ", ""), delta))
        table.add_row(axis_name(axis), *cells)
    console.print(table)

    earlier = {s.id: s for s in before.samples}
    changes = []
    for sample in after.samples:
        old = earlier.get(sample.id)
        if old is None:
            continue
        for metric_id, stat in sample.scores.items():
            previous = old.scores.get(metric_id)
            if previous is not None and previous.mean is not None and stat.mean is not None and abs(stat.mean - previous.mean) >= 0.25:
                changes.append((abs(stat.mean - previous.mean), sample.id, metric_id, previous.mean, stat.mean))
    if changes:
        detail = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False, title=t("compare.changed"), title_justify="left")
        for name in ("id", "Metric", "Before", "After", "Δ"):
            detail.add_column(name, justify="right" if name in ("Before", "After", "Δ") else "left")
        for _, sample_id, metric_id, a, b in sorted(changes, reverse=True)[:top]:
            detail.add_row(sample_id, metric_id, fmt(a), fmt(b), _delta(a, b))
        console.print(detail)
    else:
        console.print(Text(t("compare.no_changes"), style=banner.MUTED))
    only = len(set(earlier) ^ {s.id for s in after.samples})
    if only:
        console.print(Text(t("compare.unmatched", n=only), style=banner.MUTED))


def find_sample(result: EvalResult, key: str) -> SampleResult | None:
    """Find a sample by id, falling back to its index."""
    for sample in result.samples:
        if sample.id == key:
            return sample
    if key.isdigit():
        index = int(key)
        for sample in result.samples:
            if sample.index == index:
                return sample
    return None


SAMPLE_LIST_ROWS = 15


def _axis_means(result: EvalResult, sample: SampleResult) -> dict[str, float | None]:
    """Mean score per axis for one sample: the Average-column metrics, or every metric on the axis if none ran."""
    means = {}
    for axis in AXES:
        on_axis = [item.metric_id for item in result.summary if item.axis == axis]
        chosen = [m for m in on_axis if in_axis_average(m)] or on_axis
        values = [sample.scores[m].mean for m in chosen if sample.scores[m].mean is not None]
        means[axis] = sum(values) / len(values) if values else None
    return means


def print_sample_list(console: Console, result: EvalResult, everything: bool = False) -> None:
    """List samples with their axis scores, lowest average first, flagging missing scores and errors."""
    axes = [a for a in AXES if any(item.axis == a for item in result.summary)]
    rows = []
    for sample in result.samples:
        means = _axis_means(result, sample)
        values = [means[a] for a in axes if means[a] is not None]
        flags = []
        if any(r.score is None and not r.error for r in sample.results):
            flags.append(t("show.flag_unscored"))
        if any(r.error for r in sample.results):
            flags.append(t("show.flag_error"))
        rows.append((sum(values) / len(values) if values else -1.0, sample, means, flags))
    rows.sort(key=lambda row: row[0])

    console.print()
    console.print(Text(t("show.list_title"), style="bold"))
    table = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    table.add_column("Sample")
    table.add_column("Query", max_width=36, no_wrap=True, overflow="ellipsis")
    for axis in axes:
        table.add_column(axis_name(axis), justify="right")
    table.add_column("")
    shown = rows if everything else rows[:SAMPLE_LIST_ROWS]
    for _, sample, means, flags in shown:
        table.add_row(sample.id, sample.query, *(fmt(means[a]) for a in axes), Text(", ".join(flags), style=UNSURE))
    console.print(table)
    if len(shown) < len(rows):
        console.print(Text(t("show.more", n=len(rows) - len(shown)), style=banner.MUTED))
    console.print(Text(t("show.list_hint"), style=banner.MUTED))


def metrics_matching(result: EvalResult, only: str | None) -> list[str]:
    """Return the result's metrics matching a framework (``ragas``), an axis (``groundedness``) or a metric id."""
    metric_ids = [item.metric_id for item in result.summary]
    if not only:
        return metric_ids
    key = only.lower()
    return [m for m in metric_ids if m == key or m.split(".", 1)[0] == key or get_metric(m).axis == key]


def _runs_note(stat: Stat) -> str:
    """Return the per-run scores when the runs differ or some run has no score, else an empty string."""
    if len(stat.runs) < 2 or (None not in stat.runs and len(set(stat.runs)) == 1):
        return ""
    return t("sample.runs", runs=", ".join(fmt(v) if v is not None else t("sample.no_score") for v in stat.runs))


def print_sample_scores(console: Console, result: EvalResult, sample: SampleResult, metric_ids: list[str]) -> None:
    """Print the sample's axis × framework score table for the given metrics."""
    frameworks = [f for f in FRAMEWORKS if any(m.startswith(f + ".") for m in metric_ids)]
    table = Table(box=box.SIMPLE_HEAD, header_style=banner.ACCENT, pad_edge=False)
    table.add_column("")
    for framework in frameworks:
        table.add_column(column_label(framework), justify="right")
    by_cell = {(get_metric(m).axis, m.split(".", 1)[0]): m for m in metric_ids}
    for axis in AXES:
        if any(a == axis for a, _ in by_cell):
            table.add_row(axis_name(axis), *(fmt(sample.scores[by_cell[(axis, f)]].mean) if (axis, f) in by_cell else "" for f in frameworks))
    console.print(table)


def unit_mark(metric_id: str, unit: Unit) -> Text:
    """Return the mark shown before a judged unit: ✓ pass, ✗ fail, △ partial, or the score for scored units."""
    verdict = unit.verdict
    if unit.type == "truth":
        return Text(t("unit.fact"), style=banner.MUTED)
    if isinstance(verdict, str) and verdict in PASS_VERDICTS | PARTIAL_VERDICTS | FAIL_VERDICTS:
        mark, style = ("✓", GOOD) if verdict in PASS_VERDICTS else ("△", UNSURE) if verdict in PARTIAL_VERDICTS else ("✗", BAD)
        return Text.assemble((mark, style), (f" {verdict}", banner.MUTED))
    if unit.type == "judge":
        return Text(f"{verdict}/2" if verdict is not None else t("unit.failed"), style=UNSURE if verdict is None else "")
    if unit.type == "generated_question":
        mark = Text(t("unit.evasive") if verdict == 1 else "", style=BAD)
        return Text.assemble(mark, (f" {unit.score:.2f}" if unit.score is not None else "", ""))
    if verdict in (1, "yes"):
        return Text("✓", style=GOOD)
    if verdict in (0, "no"):
        return Text("✗", style=BAD)
    if verdict == "borderline":
        return Text("△", style=UNSURE)
    if unit.score is not None:
        top = 3 if metric_id.startswith("trulens.") else 1
        ratio = unit.score / top
        style = GOOD if ratio >= 0.67 else UNSURE if ratio >= 0.34 else BAD
        return Text(f"{unit.score:g}/{top}", style=style)
    return Text("·", style=banner.MUTED)


_SCORE_LINE = re.compile(r"^\s*Score:\s*\S+\s*$", re.MULTILINE)


def clean_reason(reason: str) -> str:
    """Strip the trailing "Score: N" line from TruLens reasons. Display only; result files keep the original."""
    return _SCORE_LINE.sub("", reason).strip()


def _first_run(sample: SampleResult, metric_id: str) -> MetricResult | None:
    runs = [r for r in sample.results if r.metric_id == metric_id]
    return min(runs, key=lambda r: r.run) if runs else None


def print_sample(console: Console, result: EvalResult, key: str, only: str | None = None) -> bool:
    """Print one sample's scores and per-metric judgments, optionally narrowed by :func:`metrics_matching`.

    Returns False if no sample or metric matches.
    """
    sample = find_sample(result, key)
    if sample is None:
        console.print(Text(t("sample.not_found", key=key, last=len(result.samples) - 1), style=BAD))
        return False
    metric_ids = metrics_matching(result, only)
    if not metric_ids:
        console.print(Text(t("show.no_metric", filter=only), style=BAD))
        return False

    console.print()
    console.print(Text.assemble((f"{t('sample.title')} {sample.index}", "bold"), (f"  id {sample.id}", banner.MUTED)))
    console.print(Text.assemble(("query: ", banner.MUTED), sample.query or t("sample.none")))
    print_sample_scores(console, result, sample, metric_ids)
    if result.repeats > 1:
        console.print(Text(t("sample.first_run", n=result.repeats), style=banner.MUTED))

    for metric_id in metric_ids:
        metric_result = _first_run(sample, metric_id)
        if metric_result is None:
            continue
        console.print()
        stat = sample.scores[metric_id]
        header = Text.assemble((metric_id, banner.ACCENT), ("  ", ""), (fmt_stat(stat), "bold"))
        if note := _runs_note(stat):
            header.append(f"  {note}", style=UNSURE)
        console.print(header)
        if metric_result.error:
            console.print(Text(f"  {t('sample.error')} {metric_result.error}", style=BAD))
            continue
        if metric_result.reason:
            console.print(Text(f"  {metric_result.reason}", style=banner.MUTED))
        for unit in metric_result.units:
            line = Text.assemble("  ", unit_mark(metric_id, unit), " ", unit.text)
            if unit.core:
                line.append("  core", style=banner.MUTED)
            if unit.context_ids:
                line.append(f"  [{', '.join(unit.context_ids)}]", style=banner.MUTED)
            console.print(line)
            if unit.reason and clean_reason(unit.reason):
                console.print(Text(f"      {clean_reason(unit.reason)}", style=banner.MUTED))
    return True


def format_error_lines(error) -> list[banner.Line]:
    """Explain a `DataFormatError` in the UI language, followed by examples of the expected input format."""
    # JSON parse errors and all JSONL/CSV errors point at a line; other JSON errors point at a sample in the list.
    by_sample = error.path.suffix.lower() == ".json" and error.kind != "json"
    where = t("format.where_sample" if by_sample else "format.where_line", n=error.line) if error.line else ""
    message = t(f"format.{error.kind}", file=error.path.name, where=where, detail=error.detail)
    jsonl = '{"id": "hr-01", "query": "경조사 휴가는 며칠인가요?", "contexts": ["결혼 시 5일을 준다."], "answer": "5일입니다."}'
    csv_rows = ["id,query,context_1,context_2,answer", "hr-01,경조사 휴가는 며칠인가요?,결혼 시 5일을 준다.,,5일입니다."]
    fields = [("query", t("format.guide_query")), ("contexts", t("format.guide_contexts")), ("answer", t("format.guide_answer"))]
    return [
        [(message, BAD)],
        [],
        [(t("format.guide_title"), "bold")],
        [],
        [("  " + t("format.guide_jsonl"), banner.MUTED)],
        [("    " + jsonl, banner.TEXT)],
        [],
        [("  " + t("format.guide_csv"), banner.MUTED)],
        *[[("    " + row, banner.TEXT)] for row in csv_rows],
        [],
        *[[(f"  {name:<10}", banner.MODEL), (desc, banner.MUTED)] for name, desc in fields],
        [("  " + t("format.guide_optional"), banner.MUTED)],
    ]
