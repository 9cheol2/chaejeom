"""Interactive session state and command dispatch."""

from pathlib import Path

import openai
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.folders import OUTPUT_DIR
from chaejeom.cli.i18n import LANGUAGES, get_language, set_language, t
from chaejeom.cli.interactive.commands import COMMANDS, LANGUAGE_ALIASES, QUOTES, USAGE, describe
from chaejeom.cli.interactive.config import ConfigCommands
from chaejeom.cli.interactive.data import DataCommands
from chaejeom.cli.interactive.domain import DomainCommands
from chaejeom.cli.interactive.metrics import MetricCommands
from chaejeom.cli.interactive.models import ModelCommands
from chaejeom.cli.interactive.prompts import PromptCommands
from chaejeom.cli.interactive.run import RunCommands
from chaejeom.cli.settings import save_settings
from chaejeom.config import EvalConfig
from chaejeom.data import DataFormatError
from chaejeom.evaluate import select_metrics
from chaejeom.results import EvalResult
from chaejeom.schema import EvalSample


class Session(DataCommands, MetricCommands, ModelCommands, DomainCommands, PromptCommands, RunCommands, ConfigCommands):
    """State of one interactive session; each mixin implements one command group."""

    def __init__(self, console: Console, config: EvalConfig):
        self.console = console
        self.config = config
        self.samples: list[EvalSample] = []
        self.data_path: Path | None = None
        self.selected = self._initial_selection()
        self.repeats = config.runs
        self.domain_path: str | None = config.domain
        self.prompt_paths: dict[str, str] = dict(config.prompts)
        self.exit_armed = False
        self.result: EvalResult | None = None

    def _initial_selection(self) -> dict[str, dict]:
        if self.config.metrics or self.config.axis or self.config.preset:
            return select_metrics(self.config.metrics, self.config.axis, self.config.preset)
        return select_metrics(preset="all")

    def status(self, width: int) -> list[banner.Line]:
        """Return the status lines shown below the input box."""
        grid = views.metrics_grid(self.selected)
        prompts = ", ".join(m.split(".", 1)[1] for m in self.prompt_paths)
        return banner.status_lines(
            width, self.config.judge.model, self.judge_setting(), self.config.embedding.model, grid, self.repeats, self.domain_name(), prompts
        )

    def commands(self) -> list[str]:
        """Return the commands available for the current judge model.

        Reasoning models hide ``/temperature``; other models hide ``/effort``.
        """
        hidden = "/temperature" if self.is_reasoning() else "/effort"
        return [c for c in COMMANDS if c != hidden]

    def info(self, message: str) -> None:
        self.console.print(Text.assemble(*banner.highlight(message)))

    def error(self, message: str) -> None:
        self.console.print(Text(message, style=views.BAD))

    def handle(self, text: str) -> bool:
        """Handle one line of input and return False when the session should end.

        Errors raised by a command are printed instead of propagated, so a
        failing command never ends the session.
        """
        text = text.strip()
        if not text:
            return True
        if not text.startswith("/"):
            word = text.split()[0].lower()
            if word in ("exit", "quit"):
                return False
            # Input without a leading "/" is a data path, unless it is a bare command name like
            # "help" that is not also an existing file; then point the user to "/help".
            if f"/{word}" in COMMANDS and not Path(text.strip(QUOTES)).expanduser().exists():
                self.info(t("bare_command", command=f"/{word}"))
                return True
            text = f"/data {text}"
        command, _, arg = text.partition(" ")
        arg = arg.strip()
        if command in ("/exit", "/quit"):
            return False
        handlers = {
            "/data": self.load_data,
            "/metrics": self.choose_metrics,
            "/model": self.choose_model,
            "/temperature": self.choose_temperature,
            "/effort": self.choose_effort,
            "/embedding": self.choose_embedding,
            "/domain": self.choose_domain,
            "/prompt": self.choose_prompt,
            "/run": self.run,
            "/show": self.show,
            "/runs": self.set_repeats,
            "/config": self.load_config,
            "/language": self.choose_language,
            "/help": self.help,
        }
        handler = handlers.get(command)
        if handler is None:
            self.error(t("unknown_command", command=command))
            return True
        try:
            handler(arg)
        except DataFormatError as e:
            for line in views.format_error_lines(e):
                self.console.print(Text.assemble(*line))
        except (yaml.YAMLError, ValidationError) as e:
            self.error(t("config.invalid", error=views.short_error(e)))
        except (ValueError, FileNotFoundError, ImportError, KeyError, TypeError) as e:
            self.error(views.short_error(e))
        except openai.OpenAIError as e:
            self.error(t("provider_error", error=e, env="OPENAI_API_KEY"))
        except KeyboardInterrupt:
            self.info(t("cancelled"))
        except Exception as e:  # noqa: BLE001 - one unexpected error must not end the session.
            self.error(t("unexpected_error", error=f"{type(e).__name__}: {e}"))
        return True

    def choose_language(self, arg: str) -> None:
        """Switch the UI language and remember it for later sessions."""
        from chaejeom.cli.picker import pick_one

        if arg:
            language = LANGUAGE_ALIASES.get(arg.lower(), arg)
        else:
            language = pick_one(t("language.select"), list(LANGUAGES.items()), get_language())
            if language is None:
                self.info(t("cancelled"))
                return
        set_language(language)
        self.config.language = language
        save_settings({"language": language})
        self.restart_screen()
        self.info(t("language.set"))

    def restart_screen(self) -> None:
        """Clear the screen and redraw the header in the current language; session state is kept."""
        self.console.clear()
        banner.print_header(self.console, self.config.judge.model, self.config.embedding.model)
        self.console.print()

    def help(self, arg: str) -> None:
        table = Table(box=None, pad_edge=False, header_style=banner.LABEL)
        table.add_column(t("help.usage"), style=banner.ACCENT)
        table.add_column(t("help.description"))
        for command in self.commands():
            # Wrap in Text so "[...]" in the usage is not parsed as rich markup.
            table.add_row(Text(USAGE[command]), Text(describe(command)))
        self.console.print(table)
        self.console.print()
        self.info(t("help.note"))
        self.info(t("help.results", folder=OUTPUT_DIR))
