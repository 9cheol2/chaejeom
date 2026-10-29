"""Where the CLI reads evaluation data and writes results."""

from datetime import datetime
from pathlib import Path

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
DATA_SUFFIXES = (".jsonl", ".json", ".csv")


def input_files() -> list[Path]:
    """Return the data files in the input folder, sorted by name."""
    if not INPUT_DIR.is_dir():
        return []
    return sorted(p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in DATA_SUFFIXES)


def result_paths(data: Path | None, now: datetime | None = None) -> tuple[Path, Path]:
    """Return the JSON and CSV paths for a run: ``output/<data file name>_<YYYYMMDD-HHMMSS>.json`` and ``.csv``."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    # Appended as text, not with with_suffix(): a dot in the data file name ("samples.v2") is not an extension.
    name = f"{data.stem if data else 'result'}_{stamp}"
    return OUTPUT_DIR / f"{name}.json", OUTPUT_DIR / f"{name}.csv"
