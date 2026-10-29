"""Main loop of the interactive shell."""

from rich.console import Console
from rich.text import Text

from chaejeom.cli import banner
from chaejeom.cli.i18n import set_language, t
from chaejeom.cli.interactive.command_input import read_command
from chaejeom.cli.interactive.commands import EXIT_ARMED
from chaejeom.cli.interactive.session import Session
from chaejeom.cli.settings import load_settings
from chaejeom.config import EvalConfig, load_config, load_dotenv


def run_interactive(config_path: str | None = None) -> int:
    """Run the interactive shell until the user exits and return the exit code."""
    load_dotenv()
    console = Console()
    config = load_config(config_path) if config_path else EvalConfig()
    # Without a language in the config file, reuse the UI language picked last time.
    if "language" not in config.model_fields_set:
        config.language = load_settings().get("language", config.language)
    set_language(config.language)
    session = Session(console, config)
    banner.print_header(console, config.judge.model, config.embedding.model)
    console.print()
    while True:
        text = read_command(session)
        if text is None:
            break
        if text == EXIT_ARMED:
            session.exit_armed = True
            console.print(Text(t("exit.confirm"), style=banner.MUTED))
            continue
        session.exit_armed = False
        console.print(Text.assemble(("> ", banner.PROMPT), text))
        if not session.handle(text):
            break
        console.print()
    return 0
