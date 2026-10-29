"""Command-line entry point: ``chaejeom run``, ``compare`` and ``list``, or interactive mode with no subcommand."""

import argparse
import asyncio
import sys
from pathlib import Path

import openai
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.text import Text

from chaejeom import __version__
from chaejeom.cli import views
from chaejeom.cli.folders import INPUT_DIR, input_files, result_paths
from chaejeom.cli.i18n import set_language, t
from chaejeom.config import apply_domain, apply_prompts, load_config, load_dotenv
from chaejeom.data import DataFormatError, load_samples
from chaejeom.evaluate import aevaluate, needs_embeddings, select_metrics
from chaejeom.metrics import get_metric
from chaejeom.pricing import estimate_usd, sample_stats
from chaejeom.results import EvalResult


def enable_windows_colors() -> None:
    """Enable VT processing on the classic Windows console (cmd, PowerShell).

    Without it rich falls back to 16 colours, so the logo and UI look different from Windows Terminal. With VT
    processing on, Windows 10+ consoles render truecolor and the colours match in every terminal.
    """
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    for std_handle in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
        handle = kernel32.GetStdHandle(std_handle)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def _print_progress(done: int, total: int) -> None:
    print(f"\r{t('run.progress')} {done}/{total}", end="", file=sys.stderr, flush=True)


def _output_paths(out: str) -> tuple[Path, Path]:
    """Return the JSON and CSV result paths, keeping them distinct even when ``--out`` ends in .csv.

    A dot in a name without a result extension ("out/run.v2") is kept, not read as an extension.
    """
    path = Path(out)
    if path.suffix.lower() == ".csv":
        return path.with_suffix(".json"), path
    if path.suffix.lower() == ".json":
        return path, path.with_suffix(".csv")
    return path.with_name(path.name + ".json"), path.with_name(path.name + ".csv")


def _only_input_file() -> Path | None:
    """Return the single data file in the input folder, or print why there is none to use."""
    files = input_files()
    if len(files) == 1:
        return files[0]
    print(t("run.data_needed", folder=INPUT_DIR, files=", ".join(f.name for f in files) or "-"), file=sys.stderr)
    return None


def _run(args: argparse.Namespace) -> int:
    load_dotenv()
    config = load_config(args.config)
    set_language(config.language)
    selected = apply_prompts(apply_domain(select_metrics(config.metrics, config.axis, config.preset), config.domain), config.prompts)
    if not config.domain and any(m.startswith("chaejeom.") for m in selected):
        print(t("domain.missing_warning"), file=sys.stderr)
    for line in views.data_flow_warnings(config, selected):
        print(line, file=sys.stderr)
    data = Path(args.data) if args.data else _only_input_file()
    if data is None:
        return 2
    notices: list[tuple[str, str]] = []
    samples = load_samples(data, notices)
    for kind, detail in notices:
        print(t(f"data.notice.{kind}", detail=detail), file=sys.stderr)
    if args.limit is not None:
        samples = samples[: args.limit]
    repeats = config.runs if args.runs is None else args.runs
    estimate = estimate_usd(list(selected), sample_stats(samples), len(samples), repeats, config.judge.model)
    if estimate is not None:
        print(t("cost.estimate", usd=views.format_usd(estimate), model=config.judge.model), file=sys.stderr)
    try:
        result = asyncio.run(
            aevaluate(
                samples,
                config.create_llm(),
                metrics=[{metric_id: options} for metric_id, options in selected.items()],
                embeddings=config.create_embeddings() if needs_embeddings(selected) else None,
                concurrency=config.concurrency,
                repeats=repeats,
                cache=False if args.no_cache or not config.cache else config.cache_dir,
                on_progress=_print_progress,
                label=args.label,
            )
        )
    except openai.OpenAIError as e:
        print(f"\n{t('provider_error', error=e, env='OPENAI_API_KEY')}", file=sys.stderr)
        return 1
    print(file=sys.stderr)
    if failure := views.all_failed(result):
        # A result with no scores at all is not worth saving; exit non-zero so CI notices the failure.
        print(t("run.all_failed", error=failure), file=sys.stderr)
        return 1
    json_path, csv_path = _output_paths(args.out) if args.out else result_paths(data)
    result.to_json(json_path)
    result.to_csv(csv_path)
    views.print_summary(Console(), result)
    print(f"{t('run.saved')} {json_path}, {csv_path}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    before = EvalResult.model_validate_json(Path(args.before).read_text(encoding="utf-8"))
    after = EvalResult.model_validate_json(Path(args.after).read_text(encoding="utf-8"))
    views.print_compare(Console(), before, after, args.before, args.after)
    return 0


def _list(args: argparse.Namespace) -> int:
    for metric_id in views.ordered_metrics():
        metric = get_metric(metric_id)
        inputs = ", ".join(f for f in ("query", "contexts", "answer", "embeddings") if f in metric.requires)
        print(f"{metric_id:<32} {views.axis_name(metric.axis):<18}  ({t('grid.needs', inputs=inputs)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the ``chaejeom`` command and return the process exit code."""
    parser = argparse.ArgumentParser(
        prog="chaejeom",
        description="RAG evaluation toolkit for Korean. Run without arguments to start interactive mode.",
    )
    parser.add_argument("--version", action="version", version=f"chaejeom {__version__}")
    parser.add_argument("-c", "--config", dest="start_config", metavar="FILE", help="Config file (YAML) for interactive mode")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run one evaluation with a config file and data")
    run.add_argument("--config", required=True, metavar="FILE", help="Config file (YAML)")
    run.add_argument("--data", metavar="FILE", help="Evaluation data (JSONL, JSON or CSV). Default: the only data file in input/")
    run.add_argument("--out", metavar="FILE", help="Result file (default: output/<data file name>_<date-time>.json). A .csv with the same name is saved too")
    run.add_argument("--runs", "--repeats", dest="runs", type=int, metavar="N", help="Number of runs. Overrides runs in the config (default: 3)")
    run.add_argument("--limit", type=int, metavar="N", help="Evaluate only the first N samples, for example to check the cost")
    run.add_argument("--label", help="A name for this run, saved in the result file (for example: retriever v1.3)")
    run.add_argument("--no-cache", action="store_true", help="Ignore cached LLM responses and call the model again")
    run.set_defaults(func=_run)

    compare = sub.add_parser("compare", help="Compare two result files")
    compare.add_argument("before", metavar="BEFORE", help="Earlier result file (JSON)")
    compare.add_argument("after", metavar="AFTER", help="Later result file (JSON)")
    compare.set_defaults(func=_compare)

    lst = sub.add_parser("list", help="List available metrics")
    lst.set_defaults(func=_list)

    args = parser.parse_args(argv)
    enable_windows_colors()
    try:
        if args.command is None:
            from chaejeom.cli.interactive import run_interactive

            return run_interactive(args.start_config)
        if getattr(args, "runs", None) is not None and args.runs < 1 or getattr(args, "limit", None) is not None and args.limit < 1:
            raise ValueError(t("run.invalid_number"))
        return args.func(args)
    except DataFormatError as e:
        console = Console(stderr=True)
        for line in views.format_error_lines(e):
            console.print(Text.assemble(*line))
        return 1
    except (yaml.YAMLError, ValidationError) as e:
        print(f"\n{t('config.invalid', error=views.short_error(e))}", file=sys.stderr)
        return 1
    except (ValueError, FileNotFoundError, ImportError, KeyError, TypeError) as e:
        print(f"\n{t('sample.error')} {views.short_error(e)}", file=sys.stderr)
        return 1
    except openai.OpenAIError as e:
        print(f"\n{t('provider_error', error=e, env='OPENAI_API_KEY')}", file=sys.stderr)
        return 1
