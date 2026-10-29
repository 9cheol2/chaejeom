"""Command input box rendered with prompt_toolkit."""

from typing import TYPE_CHECKING

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.buffer import Buffer, CompletionState
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import BeforeInput, Processor, Transformation, TransformationInput
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets.base import Border, Frame

from chaejeom.cli import banner
from chaejeom.cli.banner import ptk_style, to_fragments
from chaejeom.cli.i18n import t
from chaejeom.cli.interactive.commands import COMMANDS, EXIT_ARMED, describe

if TYPE_CHECKING:
    from chaejeom.cli.interactive.session import Session

STYLE = Style.from_dict(
    {
        "frame.border": f"fg:{banner.BORDER}",
        "prompt": f"fg:{banner.MODEL} bold",
        "placeholder": f"fg:{banner.MUTED}",
    }
)


class Placeholder(Processor):
    """Shows a dimmed hint while the input is empty."""

    def __init__(self, text: str):
        self.text = text

    def apply_transformation(self, ti: TransformationInput) -> Transformation:
        if not ti.document.text and ti.lineno == 0:
            return Transformation([*ti.fragments, ("class:placeholder", self.text)])
        return Transformation(ti.fragments)


def _join_lines(lines: list[banner.Line]) -> banner.Line:
    joined: banner.Line = []
    for i, line in enumerate(lines):
        joined += [("\n", "")] * (i > 0) + line
    return joined


def _rounded_frame() -> None:
    """Use rounded corners for prompt_toolkit frames (patches the global ``Border`` class)."""
    Border.HORIZONTAL, Border.VERTICAL = "─", "│"
    Border.TOP_LEFT, Border.TOP_RIGHT = "╭", "╮"
    Border.BOTTOM_LEFT, Border.BOTTOM_RIGHT = "╰", "╯"


def command_menu(state: CompletionState | None) -> StyleAndTextTuples:
    """Render the command menu shown below the input box.

    Only the selected row is highlighted, with no background color. Before any
    selection the first row is highlighted.
    """
    if state is None or not state.completions:
        return []
    width = max(len(c.text) for c in state.completions)
    current = state.complete_index or 0
    out: StyleAndTextTuples = []
    for i, completion in enumerate(state.completions):
        selected = i == current
        description = describe(completion.text) if completion.text in COMMANDS else ""
        out.append((ptk_style(banner.ACCENT if selected else banner.TEXT), f" {'›' if selected else ' '} {completion.text:<{width}}"))
        out.append((ptk_style(banner.MODEL if selected else banner.MUTED), f"   {description}\n"))
    return out


def read_command(session: "Session") -> str | None:
    """Show the input box with the status lines below it and read one command.

    Typing "/" replaces the status lines with a command menu; arrow keys select
    and Enter runs the selected command. Without a selection, Enter runs a
    command prefix only when it matches exactly one command, so "/r" does not
    start "/run".

    Returns:
        The entered text, ``EXIT_ARMED`` for Ctrl+C in an empty box, or None
        for Ctrl+D or a second Ctrl+C. Ctrl+C with text just clears the input.
    """
    _rounded_frame()
    completer = WordCompleter(session.commands, sentence=True)
    buffer = Buffer(completer=completer, complete_while_typing=True, multiline=False)
    input_window = Window(
        BufferControl(buffer=buffer, input_processors=[BeforeInput(" > ", style="class:prompt"), Placeholder(t("placeholder"))]),
        height=1,
    )
    columns = lambda: get_app().output.get_size().columns  # noqa: E731
    menu_open = Condition(lambda: buffer.complete_state is not None and bool(buffer.complete_state.completions))
    menu = Window(FormattedTextControl(lambda: command_menu(buffer.complete_state)), dont_extend_height=True)
    status = Window(FormattedTextControl(lambda: to_fragments(_join_lines(session.status(columns())))), dont_extend_height=True)
    body = HSplit(
        [
            Frame(input_window, style="class:frame"),
            ConditionalContainer(menu, filter=menu_open),
            ConditionalContainer(status, filter=~menu_open),
        ]
    )

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        state = buffer.complete_state
        typed = buffer.text.strip()
        if state and state.completions:
            if state.current_completion is not None:
                event.app.exit(result=state.current_completion.text)
                return
            names = [c.text for c in state.completions]
            if typed in names or len(names) == 1:
                event.app.exit(result=typed if typed in names else names[0])
            return
        # The menu may not be computed yet; still run an unambiguous prefix such as "/he".
        matches = [c for c in session.commands() if c.startswith(typed)] if typed.startswith("/") and " " not in typed else []
        if len(matches) > 1 and typed not in matches:
            return
        event.app.exit(result=matches[0] if matches and typed not in matches else buffer.text)

    @kb.add("down", filter=menu_open)
    def _(event):
        # The first row is already highlighted before any selection, so the first Down moves to the second.
        state = buffer.complete_state
        if state.complete_index is None:
            buffer.go_to_completion(min(1, len(state.completions) - 1))
        else:
            buffer.complete_next()

    @kb.add("c-c")
    def _(event):
        if buffer.text:
            buffer.reset()
            return
        event.app.exit(result=None if session.exit_armed else EXIT_ARMED)

    @kb.add("c-d")
    def _(event):
        event.app.exit(result=None)

    app: Application = Application(
        layout=Layout(body, focused_element=input_window),
        key_bindings=kb,
        style=STYLE,
        full_screen=False,
        erase_when_done=True,
    )
    return app.run()
