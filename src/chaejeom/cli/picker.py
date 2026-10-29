"""prompt_toolkit pickers: the /metrics grid, single-choice lists such as /model, and one-line inputs.

The /metrics grid has one row per axis and one column per framework, with one metric per cell. A row label toggles
the whole axis, a column label the whole framework, and "All" in the top-left corner every metric. The Runs row at
the bottom sets the repeat count.
"""

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer, CompletionState
from prompt_toolkit.completion import Completer, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import BeforeInput

from chaejeom.cli import banner
from chaejeom.cli.banner import ptk_style, to_fragments
from chaejeom.cli.i18n import t
from chaejeom.cli.views import AXES, FRAMEWORK_LABELS, FRAMEWORKS, METRIC_NAMES, axis_name, ordered_metrics
from chaejeom.metrics import get_metric

MAX_RUNS = 20
RUNS_ROW = len(AXES) + 1
LABEL_WIDTH = 21
CELL_WIDTH = 12


def _hint(text: str) -> StyleAndTextTuples:
    return to_fragments(banner.key_hint(text))


def metric_at(axis: str, framework: str) -> str:
    return next(m for m in ordered_metrics() if m.startswith(framework + ".") and get_metric(m).axis == axis)


def group(row: int, col: int) -> set[str]:
    """Return the metrics a grid cell covers: row 0 is a whole framework, column 0 a whole axis, (0, 0) everything."""
    axes = AXES if row == 0 else [AXES[row - 1]]
    frameworks = FRAMEWORKS if col == 0 else [FRAMEWORKS[col - 1]]
    return {metric_at(a, f) for a in axes for f in frameworks}


def toggle_group(chosen: set[str], ids: set[str]) -> set[str]:
    """Turn ``ids`` off if all of them are selected, otherwise select them all."""
    return chosen - ids if ids <= chosen else chosen | ids


def _describe(row: int, col: int, repeats: int) -> str:
    if row == RUNS_ROW:
        return t("grid.runs_many") if repeats > 1 else t("grid.runs_one")
    if row == 0 and col == 0:
        return t("grid.toggle_all")
    if row == 0:
        return t("grid.toggle_framework", name=FRAMEWORK_LABELS[FRAMEWORKS[col - 1]])
    if col == 0:
        return t("grid.toggle_axis", name=axis_name(AXES[row - 1]))
    metric_id = metric_at(AXES[row - 1], FRAMEWORKS[col - 1])
    inputs = ", ".join(f for f in ("query", "contexts", "answer", "embeddings") if f in get_metric(metric_id).requires)
    return f"{FRAMEWORK_LABELS[FRAMEWORKS[col - 1]]} {METRIC_NAMES[metric_id]}   {t('grid.needs', inputs=inputs)}"


def render(chosen: set[str], row: int, col: int, repeats: int) -> StyleAndTextTuples:
    def cell(text: str, width: int, at: bool, style: str) -> list[tuple[str, str]]:
        return [(ptk_style(banner.ACCENT if at else style), banner.pad(f"{'›' if at else ' '}{text}", width))]

    out: StyleAndTextTuples = [(ptk_style("bold"), t("grid.title") + "\n"), *_hint(t("grid.help")), ("", "\n\n")]
    out += cell("All", LABEL_WIDTH, row == 0 and col == 0, banner.LABEL)
    for c, framework in enumerate(FRAMEWORKS, start=1):
        out += cell(FRAMEWORK_LABELS[framework], CELL_WIDTH, row == 0 and col == c, banner.TEXT)
    out.append(("", "\n"))
    for r, axis in enumerate(AXES, start=1):
        out += cell(axis_name(axis), LABEL_WIDTH, row == r and col == 0, banner.TEXT)
        for c, framework in enumerate(FRAMEWORKS, start=1):
            on = metric_at(axis, framework) in chosen
            out += cell("[✓]" if on else "[ ]", CELL_WIDTH, row == r and col == c, banner.MODEL if on else banner.MUTED)
        out.append(("", "\n"))
    out.append(("", "\n"))
    out += cell("Runs", LABEL_WIDTH, row == RUNS_ROW, banner.TEXT)
    out.append((ptk_style(banner.ACCENT if row == RUNS_ROW else banner.MODEL), f"‹ {repeats} ›"))
    out.append(("", "\n\n"))
    out.append((ptk_style(banner.MUTED), f" {_describe(row, col, repeats)}\n"))
    out.append((ptk_style(banner.MUTED), f" {t('grid.count', n=len(chosen), total=len(ordered_metrics()))}\n"))
    return out


def pick_metrics(selected: set[str], repeats: int = 1) -> tuple[set[str], int] | None:
    """Show the metrics grid. Returns ``(metric ids, repeats)``, or None if cancelled."""
    state = {"row": 1, "col": 1, "chosen": set(selected) & set(ordered_metrics()), "repeats": repeats}
    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        state["row"] = (state["row"] - 1) % (RUNS_ROW + 1)

    @kb.add("down")
    def _(event):
        state["row"] = (state["row"] + 1) % (RUNS_ROW + 1)

    @kb.add("left")
    def _(event):
        if state["row"] == RUNS_ROW:
            state["repeats"] = max(state["repeats"] - 1, 1)
        else:
            state["col"] = (state["col"] - 1) % (len(FRAMEWORKS) + 1)

    @kb.add("right")
    def _(event):
        if state["row"] == RUNS_ROW:
            state["repeats"] = min(state["repeats"] + 1, MAX_RUNS)
        else:
            state["col"] = (state["col"] + 1) % (len(FRAMEWORKS) + 1)

    @kb.add("space")
    def _(event):
        if state["row"] != RUNS_ROW:
            state["chosen"] = toggle_group(state["chosen"], group(state["row"], state["col"]))

    @kb.add("enter")
    def _(event):
        event.app.exit(result=(set(state["chosen"]), state["repeats"]))

    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=None)

    control = FormattedTextControl(lambda: render(state["chosen"], state["row"], state["col"], state["repeats"]))
    app: Application = Application(
        layout=Layout(Window(control)),
        key_bindings=kb,
        full_screen=False,
        erase_when_done=True,
    )
    return app.run()


def render_options(title: str, options: list[tuple[str, str]], cursor: int, current: str | None) -> StyleAndTextTuples:
    width = max(banner.display_width(label) for _, label in options)
    out: StyleAndTextTuples = [(ptk_style("bold"), f"{title}\n"), *_hint(t("picker.help")), ("", "\n\n")]
    for i, (value, label) in enumerate(options):
        pointer = "›" if i == cursor else " "
        out.append((ptk_style(banner.PROMPT), f" {pointer} "))
        out.append((ptk_style("bold" if i == cursor else ""), banner.pad(label, width)))
        if value == current:
            out.append((ptk_style(banner.MUTED), f"   ({t('picker.current')})"))
        out.append(("", "\n"))
    return out


MAX_SUGGESTIONS = 8


def suggestion_menu(state: CompletionState | None) -> StyleAndTextTuples:
    """Render completion candidates below the input, marking the selected one in the accent colour (no background)."""
    if state is None or not state.completions:
        return []
    current = state.complete_index
    start = max(0, min((current or 0) - MAX_SUGGESTIONS + 1, len(state.completions) - MAX_SUGGESTIONS))
    out: StyleAndTextTuples = []
    for i, completion in enumerate(state.completions[start : start + MAX_SUGGESTIONS], start=start):
        selected = i == current
        out.append((ptk_style(banner.ACCENT if selected else banner.MUTED), f"   {'›' if selected else ' '} {completion.display_text}\n"))
    return out


def ask_value(title: str, default: str, hint: str, completer: Completer | None = None) -> str | None:
    """Prompt for one line of text, pre-filled with ``default``. Returns the text, or None if cancelled.

    With a ``completer``, candidates are listed below the input while typing and selected with Tab or ↑↓. Enter on a
    selected candidate only inserts it, so the user can keep descending into folders; Enter with no candidate
    selected submits.
    """
    buffer = Buffer(document=Document(default, len(default)), multiline=False, completer=completer, complete_while_typing=completer is not None)
    kb = KeyBindings()
    has_suggestions = Condition(lambda: buffer.complete_state is not None and bool(buffer.complete_state.completions))

    @kb.add("enter")
    def _(event):
        state = buffer.complete_state
        if state and state.current_completion:
            buffer.apply_completion(state.current_completion)
            return
        event.app.exit(result=buffer.text.strip())

    @kb.add("tab")
    def _(event):
        if buffer.complete_state:
            buffer.complete_next()
        else:
            buffer.start_completion(select_first=True)

    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=None)

    body = HSplit(
        [
            Window(FormattedTextControl([(ptk_style("bold"), title)]), height=1),
            Window(BufferControl(buffer=buffer, input_processors=[BeforeInput(" > ", style=ptk_style(banner.PROMPT))]), height=1),
            ConditionalContainer(Window(FormattedTextControl(lambda: suggestion_menu(buffer.complete_state)), dont_extend_height=True), filter=has_suggestions),
            Window(FormattedTextControl([(ptk_style(banner.MUTED), f"{hint}\n"), *_hint(t("input.help"))]), height=2),
        ]
    )
    app: Application = Application(layout=Layout(body), key_bindings=kb, full_screen=False, erase_when_done=True)
    return app.run()


def ask_path(title: str, hint: str, default: str = "") -> str | None:
    """Prompt for a file path, with Tab completion."""
    return ask_value(title, default, hint, PathCompleter(expanduser=True))


def pick_one(title: str, options: list[tuple[str, str]], current: str | None = None) -> str | None:
    """Pick one of ``options`` (``(value, label)`` pairs). Returns the value, or None if cancelled."""
    values = [value for value, _ in options]
    state = {"cursor": values.index(current) if current in values else 0}
    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        state["cursor"] = (state["cursor"] - 1) % len(options)

    @kb.add("down")
    def _(event):
        state["cursor"] = (state["cursor"] + 1) % len(options)

    @kb.add("enter")
    def _(event):
        event.app.exit(result=values[state["cursor"]])

    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=None)

    control = FormattedTextControl(lambda: render_options(title, options, state["cursor"], current))
    app: Application = Application(
        layout=Layout(Window(control)),
        key_bindings=kb,
        full_screen=False,
        erase_when_done=True,
    )
    return app.run()
