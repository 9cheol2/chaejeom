import csv
import io
import json
import re
from pathlib import Path

from pydantic import ValidationError

from chaejeom.schema import EvalSample

SAMPLE_SUFFIXES = (".jsonl", ".json", ".csv")
CONTEXT_FIELDS = {"contexts", "retrieved_contexts", "retrieval_context"}
CONTENT_FIELDS = {"query", "user_input", "input", "answer", "response", "actual_output"} | CONTEXT_FIELDS
SAMPLE_FIELDS = CONTENT_FIELDS | {"id", "metadata"}
# Ground-truth fields. All metrics are reference-free, but RAGAS/DeepEval datasets often carry
# these, so they are dropped rather than rejected. DeepEval's `context` is the ideal context,
# not retrieval output.
REFERENCE_FIELDS = {
    "reference", "reference_contexts", "ground_truth", "ground_truths", "expected_output", "expected_answer",
    "context", "golden_answer", "reference_answer",
}
_NUMBERED_CONTEXT = re.compile(r"context_(\d+)")


class DataFormatError(ValueError):
    """Raised when an input file does not match a supported sample format.

    The CLI uses ``kind``, ``line`` and ``detail`` to show a localized message and format example.

    Attributes:
        kind: One of ``extension``, ``encoding``, ``empty``, ``json``, ``not_list``,
            ``not_object``, ``csv_row``, ``no_fields``, ``invalid``.
        line: File line number for JSONL/CSV; 1-based sample index for JSON.
    """

    def __init__(self, kind: str, path: Path, line: int | None = None, detail: str = ""):
        self.kind, self.path, self.line, self.detail = kind, path, line, detail
        where = f"{path.name} {line}번째 샘플" if line else path.name
        super().__init__(f"{where}: 입력 데이터 형식이 맞지 않습니다 ({kind}{': ' + detail if detail else ''}).")


def _read_csv(path: Path, text: str) -> list[tuple[int, dict]]:
    """Read one sample per row; the first row is the header.

    Contexts come from ``context_1``, ``context_2``, ... columns or a ``contexts`` column holding
    a JSON list. ``metadata.<key>`` (or ``meta.<key>`` from a result CSV) columns are collected
    into ``metadata``. Empty cells are treated as missing.
    """
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for record in reader:
        line_no = reader.line_num
        if None in record:
            raise DataFormatError("csv_row", path, line_no)
        row: dict = {}
        numbered: list[tuple[int, str]] = []
        metadata: dict = {}
        for column, value in record.items():
            column, value = column.strip(), (value or "").strip()
            if not value:
                continue
            if match := _NUMBERED_CONTEXT.fullmatch(column):
                numbered.append((int(match.group(1)), value))
            elif column.startswith(("metadata.", "meta.")):
                metadata[column.split(".", 1)[1]] = value
            elif column in CONTEXT_FIELDS:
                row[column] = _context_cell(value)
            else:
                row[column] = value
        if numbered:
            row["contexts"] = [text for _, text in sorted(numbered)]
        if metadata:
            row["metadata"] = metadata
        if any(record.values()):
            rows.append((line_no, row))
    return rows


def _context_cell(value: str) -> list:
    """Parse a contexts cell: a JSON list yields many contexts; anything else, even text starting with "[", one."""
    if value.startswith("["):
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(data, list):
            return data
    return [value]


def _read_text(path: Path, notices: list | None) -> str:
    """Read as UTF-8 (BOM allowed); CSV falls back to CP949, Korean Excel's default encoding."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        if path.suffix.lower() != ".csv":
            raise DataFormatError("encoding", path) from None
    try:
        text = path.read_text(encoding="cp949")
    except UnicodeDecodeError:
        raise DataFormatError("encoding", path) from None
    if notices is not None:
        notices.append(("cp949", ""))
    return text


def load_samples(path: str | Path, notices: list[tuple[str, str]] | None = None) -> list[EvalSample]:
    """Load samples from JSONL (one per line), JSON (a list), or CSV (one per row).

    Ground-truth fields are dropped and other unknown fields are moved into ``metadata``.

    Args:
        path: Input file.
        notices: If given, receives ``(kind, fields)`` tuples describing these adjustments,
            where kind is ``reference_fields``, ``metadata_fields`` or ``cp949``.

    Raises:
        DataFormatError: If the file cannot be parsed into samples.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SAMPLE_SUFFIXES:
        raise DataFormatError("extension", path)
    text = _read_text(path, notices)

    rows: list[tuple[int, object]] = []
    if suffix == ".csv":
        rows = _read_csv(path, text)
    elif suffix == ".json":
        try:
            data = json.loads(text) if text.strip() else []
        except json.JSONDecodeError as e:
            raise DataFormatError("json", path, e.lineno, e.msg) from None
        if not isinstance(data, list):
            raise DataFormatError("not_list", path)
        rows = list(enumerate(data, start=1))
    else:
        # Not splitlines(): it also breaks on U+2028 and similar characters, which may occur inside a record.
        for line_no, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                continue
            try:
                rows.append((line_no, json.loads(line)))
            except json.JSONDecodeError as e:
                raise DataFormatError("json", path, line_no, e.msg) from None
    if not rows:
        raise DataFormatError("empty", path)

    samples = []
    ignored: set[str] = set()
    moved: set[str] = set()
    for line_no, row in rows:
        if not isinstance(row, dict):
            raise DataFormatError("not_object", path, line_no)
        ignored |= set(row) & REFERENCE_FIELDS
        row = {k: v for k, v in row.items() if k not in REFERENCE_FIELDS}
        if unknown := set(row) - SAMPLE_FIELDS:
            moved |= unknown
            metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
            row = {k: v for k, v in row.items() if k not in unknown} | {"metadata": {**{k: row[k] for k in unknown}, **metadata}}
        if not set(row) & CONTENT_FIELDS:
            raise DataFormatError("no_fields", path, line_no)
        try:
            samples.append(EvalSample.model_validate(row))
        except ValidationError as e:
            fields = sorted({str(err["loc"][0]) for err in e.errors() if err["loc"]})
            raise DataFormatError("invalid", path, line_no, ", ".join(fields)) from None
    if notices is not None:
        if ignored:
            notices.append(("reference_fields", ", ".join(sorted(ignored))))
        if moved:
            notices.append(("metadata_fields", ", ".join(sorted(moved))))
    return samples
