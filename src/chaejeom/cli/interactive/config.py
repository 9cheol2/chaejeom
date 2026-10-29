"""/config command."""

from pathlib import Path

import yaml
from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.i18n import get_language, set_language, t
from chaejeom.cli.interactive.commands import QUOTES
from chaejeom.config import EvalConfig, ModelConfig, load_config


class ConfigCommands:
    def load_config(self, arg: str) -> None:
        """Load a config file; ``/config save [file]`` saves the current settings instead."""
        from chaejeom.cli.picker import ask_path, pick_one

        if arg.split(" ", 1)[0].lower() == "save":
            self.save_config(arg[4:].strip(QUOTES + " "))
            return
        if not arg:
            choice = pick_one(t("config.menu"), [("load", t("config.load")), ("save", t("config.save"))])
            if choice is None:
                self.info(t("cancelled"))
                return
            if choice == "save":
                self.save_config("")
                return
            arg = ask_path(t("config.ask"), t("config.hint"))
            if not arg:
                self.info(t("cancelled"))
                return
        self.config = load_config(Path(arg.strip("'\"")).expanduser())
        if "language" in self.config.model_fields_set:
            set_language(self.config.language)
        else:
            self.config.language = get_language()
        if "domain" in self.config.model_fields_set:
            self.domain_path = self.config.domain
        if "prompts" in self.config.model_fields_set:
            self.prompt_paths = dict(self.config.prompts)
        self.selected = self._initial_selection()
        self.repeats = self.config.runs
        self.console.print(
            Text.assemble(
                (t("config.loaded") + " ", ""),
                ("model: ", banner.LABEL),
                (self.judge_label(), banner.MODEL),
                ("  │  ", banner.SEP),
                ("embedding: ", banner.LABEL),
                (self.config.embedding.model, banner.MODEL),
            )
        )
        self.print_selected()

    def current_config(self) -> dict:
        """Return the session settings as a config file mapping.

        The saved file can be loaded again with ``/config`` or ``chaejeom -c``.
        """

        def model(config: ModelConfig, options: dict) -> dict:
            return {"provider": config.provider, "model": config.model, **options}

        data = {
            "judge": model(self.config.judge, self.config.judge_options()),
            "embedding": model(self.config.embedding, self.config.embedding.options),
            "domain_model": model(self.config.domain_model, self.config.domain_model.options),
            "metrics": [m if not o else {m: o} for m, o in self.selected.items()],
            "runs": self.repeats,
            "concurrency": self.config.concurrency,
            "cache": self.config.cache,
            "cache_dir": self.config.cache_dir,
            "language": get_language(),
        }
        if self.domain_path:
            data["domain"] = self.domain_path
        if self.prompt_paths:
            data["prompts"] = dict(self.prompt_paths)
        EvalConfig.model_validate(data)
        return data

    def save_config(self, path: str) -> None:
        """Write the current settings to a YAML config file."""
        from chaejeom.cli.picker import ask_path

        if not path:
            path = ask_path(t("config.save_ask"), t("config.save_hint"), "chaejeom.yaml") or ""
            if not path:
                self.info(t("cancelled"))
                return
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(self.current_config(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.console.print(Text.assemble((t("config.saved") + " ", banner.MUTED), views.path_link(target)))
