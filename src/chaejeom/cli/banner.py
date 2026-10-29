"""Start screen of the interactive CLI, plus rich-to-prompt_toolkit style helpers.

The header shows the hat logo on the left and the name, version, judge and embedding models and working directory on
the right, followed by a rounded input box and a status footer. Screens are built as lines of ``(text, style)``
segments and printed with rich.
"""

import os
import re
import unicodedata
from pathlib import Path

from rich.console import Console
from rich.text import Text

from chaejeom.cli.i18n import t
from chaejeom.defaults import DEFAULT_RUNS

Segment = tuple[str, str]
Line = list[Segment]

TEXT = "#DAD3C6"
MUTED = "#867F74"
SEP = "#5C5043"
ACCENT = "bold #F2B45E"
RED_PEN = "#E5484D"
PROMPT = ACCENT
PATH = "#E3A964"
MODEL = "#F2B45E"
LABEL = "#6B665E"
BORDER = "#4A4D57"

MAX_WIDTH = 110

# A black gat (Korean traditional hat) seen slightly from above: a tall narrow crown, a thin wide brim, and
# straps that meet in a V at a knot. Each grid character is one terminal cell, drawn as a space with a background
# colour. Half-block characters (▀▄█) differ in width and height across fonts and terminals, but a space is always
# one cell, so the logo looks the same in cmd, PowerShell and Windows Terminal. Even the darkest shade is lighter
# than a black background so the outline stays visible; light falls from the top left.
# Keys: T crown top, H L M S D crown from left to right, N band, B brim top, E brim front edge, s strap, k knot.
# Tuples are left-to-right gradients.
HAT_COLORS: dict[str, str | tuple[str, ...]] = {
    "T": "#8E929E", "H": "#73778A", "L": "#5A5E6A", "M": "#4A4D57", "S": "#3E414A", "D": "#5E6270",
    "N": "#33363E", "B": ("#73778A", "#5A5E6A", "#46494F"), "E": ("#B4B8C4", "#9A9EAA", "#7E8290"),
    "s": "#8E929E", "k": "#B4B8C4",
}
# For 16-colour terminals. rich maps the dark greys to black, which punches holes in the hat, so only the shape is
# kept, using the greys and whites of the 16-colour palette.
HAT_COLORS_16: dict[str, str] = {
    "T": "white", "H": "bright_black", "L": "bright_black", "M": "bright_black", "S": "bright_black", "D": "bright_black",
    "N": "bright_black", "B": "bright_black", "E": "white", "s": "white", "k": "bright_white",
}
# A terminal cell is about twice as tall as it is wide, so the brim needs only two rows.
HAT = [
    "...........TTTTT...........",
    "..........HLMMMSD..........",
    "..........HLMMMSD..........",
    "..........HLMMMSD..........",
    "..........HLMMMSD..........",
    "...BBBBBBBNNNNNNNBBBBBBB...",
    "EEEEEEEEEEEEEEEEEEEEEEEEEEE",
    ".........s.......s.........",
    "..........s.....s..........",
    "...........s...s...........",
    "............s.s............",
    ".............k.............",
    "............s.s............",
]

LOGO_INDENT = 2
LOGO_GAP = 4


def display_width(text: str) -> int:
    """Return the width of ``text`` in terminal cells, counting wide characters such as Hangul as two."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _line_width(line: Line) -> int:
    return sum(display_width(t) for t, _ in line)


def _blend(colors: tuple[str, ...], t: float) -> str:
    span = t * (len(colors) - 1)
    i = min(int(span), len(colors) - 2)
    local = span - i
    a = [int(colors[i][k : k + 2], 16) for k in (1, 3, 5)]
    b = [int(colors[i + 1][k : k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * local):02X}" for x, y in zip(a, b))


def _merge(cells: list[Segment]) -> Line:
    line: Line = []
    for ch, style in cells:
        if line and line[-1][1] == style:
            line[-1] = (line[-1][0] + ch, style)
        else:
            line.append((ch, style))
    return line


def hat_lines(color_system: str | None = "truecolor") -> list[Line]:
    """Render the hat logo, one coloured space per grid cell; empty cells keep the terminal background.

    16-colour terminals (``color_system`` "standard" or "windows") use `HAT_COLORS_16`.
    """
    last = len(HAT[0]) - 1
    few_colors = color_system in ("standard", "windows")

    def cell(r: int, c: int) -> Segment:
        key = HAT[r][c]
        if key == ".":
            return (" ", "")
        if few_colors:
            return (" ", f"on {HAT_COLORS_16[key]}")
        value = HAT_COLORS[key]
        return (" ", f"on {value if isinstance(value, str) else _blend(value, c / last)}")

    return [_merge([cell(r, c) for c in range(len(HAT[0]))]) for r in range(len(HAT))]


def _truncate_left(text: str, room: int) -> str:
    """Shorten ``text`` from the left with "…" to fit within ``room`` terminal cells."""
    if display_width(text) <= room:
        return text
    kept = ""
    for ch in reversed(text):
        if display_width(ch + kept) > room - 1:
            break
        kept = ch + kept
    return "…" + kept


def short_path(path: Path) -> str:
    home = Path.home()
    try:
        return "~/" + path.relative_to(home).as_posix()
    except ValueError:
        return path.as_posix()


def pad(text: str, width: int) -> str:
    """Pad ``text`` with spaces to ``width`` terminal cells, counting wide characters as two."""
    return text + " " * max(width - display_width(text), 0)


# End a command where its ASCII letters end rather than at a word boundary, so "/data로" (a command followed
# directly by a Korean particle) still matches.
_COMMAND = re.compile(r"(/[a-z]+(?![a-z])|^/(?=\s)|ctrl\+c)")


def highlight(text: str, base: str = MUTED, accent: str = MODEL) -> Line:
    """Style ``text`` with ``base``, highlighting commands (e.g. /data) and ctrl+c with ``accent``."""
    return [(part, accent if i % 2 else base) for i, part in enumerate(_COMMAND.split(text)) if part]


# Key names in shortcut hints. A leading "/" is the key that opens the command list.
_KEY = re.compile(r"(↑↓←→|↑↓|←→|Ctrl\+C|Enter|Esc|Space|Tab|^/(?=\s))")


def key_hint(text: str) -> Line:
    """Style a shortcut hint such as "Enter to confirm · Esc to cancel": key names bright, the rest muted."""
    return [(part, TEXT if i % 2 else MUTED) for i, part in enumerate(_KEY.split(text)) if part]


# Pre-release versions such as 0.1.0.dev0, 0.2.0a1 or 0.2.0rc1 get a stage label next to the version.
_RELEASE = re.compile(r"^(\d+(?:\.\d+)*)(?:\.?(dev|a|b|rc)\d*)?$")
PRE_RELEASE_LABELS = {"dev": "header.preview", "a": "header.alpha", "b": "header.beta", "rc": "header.rc"}


def display_version(version: str) -> Line:
    """Format the package version for display, labelling pre-releases (e.g. 0.1.0.dev0 becomes "v0.1.0 Preview")."""
    match = _RELEASE.match(version)
    if match is None:
        return [(f"v{version}", MUTED)]
    base, stage = match.groups()
    return [(f"v{base}", MUTED), *([(f" {t(PRE_RELEASE_LABELS[stage])}", MODEL)] if stage else [])]


def header_lines(
    width: int, judge: str, embedding: str, version: str, cwd: Path | None = None, color_system: str | None = "truecolor"
) -> list[Line]:
    """Build the header: the hat logo with name, version, models, working directory and a getting-started tip."""
    hat = hat_lines(color_system)
    room = min(width, MAX_WIDTH) - LOGO_INDENT - _line_width(hat[0]) - LOGO_GAP
    path = short_path(cwd or Path(os.getcwd()))
    labels = ["model:", "embedding:", "directory:"]
    label_width = max(display_width(label) for label in labels) + 1
    info: list[Line] = [
        [],
        [("Chaejeom CLI ", ACCENT), *display_version(version)],
        [(t("header.greeting"), TEXT)] if display_width(t("header.greeting")) <= room else [],
        [],
        [(pad(labels[0], label_width), LABEL), (judge, TEXT)],
        [(pad(labels[1], label_width), LABEL), (embedding, TEXT)],
        [(pad(labels[2], label_width), LABEL), (_truncate_left(path, room - label_width), TEXT)],
        [],
        highlight(t("header.tip")),
    ]
    return [
        [(" " * LOGO_INDENT, ""), *line, (" " * LOGO_GAP, ""), *(info[r] if r < len(info) else [])]
        for r, line in enumerate(hat)
    ]


def input_box(width: int) -> list[Line]:
    """Build a preview of the rounded input box; interactive mode draws the real one with prompt_toolkit."""
    inner = width - 2
    body: Line = [(" > ", PROMPT), (t("placeholder"), MUTED)]
    return [
        [("╭" + "─" * inner + "╮", BORDER)],
        [("│", BORDER), *body, (" " * (inner - _line_width(body)), ""), ("│", BORDER)],
        [("╰" + "─" * inner + "╯", BORDER)],
    ]


FRAMEWORK_NAMES = ("RAGAS", "DeepEval", "TruLens", "Chaejeom")


def status_lines(
    width: int,
    judge: str,
    setting: tuple[str, str],
    embedding: str,
    grid: list[tuple[str, list[bool]]],
    runs: int,
    domain: str = "none",
    prompts: str = "",
) -> list[Line]:
    """Build the status footer below the input box, with labels aligned in one column.

    The metrics rows show one axis each, with selected frameworks in brackets (``[RAGAS]``). The first row ends with
    a shortcut hint, which is dropped when the width is too small.

    Args:
        setting: Label and value shown right of the model, e.g. ``("temperature:", "0")`` or ``("effort:", "low")``.
        grid: Per-axis framework selection, as returned by ``views.metrics_grid``.
        domain: Name of the domain information used by Chaejeom metrics, or ``"none"``.
        prompts: Chaejeom metrics that use a custom prompt. The prompt row is shown only when non-empty.
    """
    labels = {key: f"{key}:" for key in ("model", "embedding", "domain", "prompt", "metrics", "runs")}
    label_width = max(display_width(text) for text in labels.values()) + 1

    def row(label: str, *values: Segment) -> Line:
        return [(" ", ""), (pad(label, label_width), LABEL), *values]

    first = row(labels["model"], (judge, MUTED), ("   " + setting[0] + " ", LABEL), (setting[1], MUTED))
    hint = key_hint(t("footer.hint"))
    if _line_width(first) + _line_width(hint) + 4 > width:
        hint = []
    first += [(" " * max(width - _line_width(first) - _line_width(hint) - 1, 1), ""), *hint]

    lines = [first, row(labels["embedding"], (embedding, MUTED)), row(labels["domain"], (domain, MUTED))]
    if prompts:
        lines.append(row(labels["prompt"], (t("status.custom_prompt", metrics=prompts), MUTED)))
    axis_width = max(display_width(axis) for axis, _ in grid) + 1
    for i, (axis, chosen) in enumerate(grid):
        cells: Line = [(pad(axis, axis_width), MUTED)]
        for name, on in zip(FRAMEWORK_NAMES, chosen):
            cells.append((pad(f"[{name}]" if on else f" {name} ", len(name) + 3), MUTED if on else SEP))
        lines.append(row(labels["metrics"] if i == 0 else "", *cells))
    lines.append(row(labels["runs"], (str(runs), MUTED)))
    return lines


def startup_lines(width: int, judge: str, embedding: str, version: str, cwd: Path | None = None) -> list[Line]:
    """Build a preview of the whole start screen."""
    width = min(width, MAX_WIDTH)
    axes = ["Groundedness", "Context relevance", "Answer relevance"]
    grid = [(axis, [True] * len(FRAMEWORK_NAMES)) for axis in axes]
    return [
        *header_lines(width, judge, embedding, version, cwd),
        [],
        *input_box(width),
        *status_lines(width, judge, ("temperature:", "0"), embedding, grid, DEFAULT_RUNS),
    ]


def print_header(console: Console, judge: str, embedding: str) -> None:
    from chaejeom import __version__

    for line in header_lines(console.width, judge, embedding, __version__, color_system=console.color_system):
        console.print(Text.assemble(*line), soft_wrap=True)


def print_startup(console: Console | None = None, judge: str = "gpt-4.1-mini", embedding: str = "text-embedding-3-large") -> None:
    from chaejeom import __version__

    console = console or Console()
    for line in startup_lines(console.width, judge, embedding, __version__):
        console.print(Text.assemble(*line), soft_wrap=True)


if __name__ == "__main__":
    print_startup()


def ptk_style(style: str) -> str:
    """Convert a rich style string such as "bold #FFB347" or "#A on #B" to prompt_toolkit format.

    Only ``bold``, a hex foreground colour and the background colour are kept.
    """
    parts = style.split()
    out = ["bold"] if "bold" in parts else []
    if "on" in parts:
        i = parts.index("on")
        out.append(f"bg:{parts[i + 1]}")
        parts = parts[:i]
    colors = [p for p in parts if p.startswith("#")]
    if colors:
        out.append(f"fg:{colors[0]}")
    return " ".join(out)


def to_fragments(line: Line) -> list[tuple[str, str]]:
    """Convert a `Line` of rich-styled segments to prompt_toolkit formatted-text fragments."""
    return [(ptk_style(style), text) for text, style in line]
