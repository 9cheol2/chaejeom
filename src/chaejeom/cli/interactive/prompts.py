"""/prompt command."""

import asyncio
from pathlib import Path

from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.i18n import t
from chaejeom.cli.interactive.commands import QUOTES
from chaejeom.customize.prompt_file import (
    PromptFile,
    PromptRevisionError,
    default_path,
    is_editable,
    load_prompt,
    revise,
    save_prompt,
)
from chaejeom.metrics import get_metric
from chaejeom.metrics.catalog import upstream_prompts
from chaejeom.metrics.chaejeom.prompts import TEMPLATES, preview


class PromptCommands:
    def choose_prompt(self, arg: str) -> None:
        """Show a metric's judge prompt and, for Chaejeom metrics, edit, load or reset it.

        Metrics ported from other frameworks keep their upstream prompts and are
        read-only. Passing a prompt file path loads that file directly.
        """
        from chaejeom.cli.picker import ask_path, pick_one

        arg = arg.strip(QUOTES)
        if Path(arg).suffix in (".yaml", ".yml"):
            self.use_prompt(load_prompt(Path(arg).expanduser()).metric, arg, t("prompt.loaded"))
            return
        metric_id = arg
        if not metric_id:
            options = [(m, f"{views.metric_label(m)}  ({m})") for f in views.FRAMEWORKS for m in views.ordered_metrics() if m.startswith(f + ".")]
            metric_id = pick_one(t("prompt.select"), options)
            if metric_id is None:
                self.info(t("cancelled"))
                return
        get_metric(metric_id)
        if not is_editable(metric_id):
            steps = upstream_prompts(metric_id)
            self.print_steps(metric_id, steps, full=False)
            self.info(t("prompt.read_only"))
            choice = pick_one(t("prompt.menu", metric=metric_id), [("full", t("prompt.full")), ("close", t("prompt.close"))])
            if choice == "full":
                self.print_steps(metric_id, steps, full=True)
            elif choice is None:
                self.info(t("cancelled"))
            return

        self.print_custom_prompt(metric_id)
        options = [("edit", t("prompt.edit")), ("load", t("prompt.load"))]
        if metric_id in self.prompt_paths:
            options.append(("reset", t("prompt.reset")))
        options += [("full", t("prompt.full")), ("close", t("prompt.close"))]
        choice = pick_one(t("prompt.menu", metric=metric_id), options)
        if choice is None:
            self.info(t("cancelled"))
        elif choice == "full":
            self.print_custom_prompt(metric_id, full=True)
        elif choice == "edit":
            self.edit_prompt(metric_id)
        elif choice == "load":
            path = ask_path(t("prompt.load_ask"), t("prompt.load_hint"))
            if not path:
                self.info(t("cancelled"))
                return
            self.use_prompt(metric_id, path.strip(QUOTES), t("prompt.loaded"))
        elif choice == "reset":
            del self.prompt_paths[metric_id]
            self.info(t("prompt.reset_done", metric=metric_id))

    def custom_template(self, metric_id: str) -> str | None:
        """Return the custom prompt template for a metric, or None if it uses the default."""
        path = self.prompt_paths.get(metric_id)
        return load_prompt(Path(path).expanduser(), metric_id).template if path else None

    def current_template(self, metric_id: str) -> str:
        """Return the template in effect: the custom prompt, else the domain's, else the built-in one."""
        profile = self.domain_profile()
        return self.custom_template(metric_id) or (profile and profile.template(metric_id)) or TEMPLATES[metric_id]

    def print_steps(self, metric_id: str, steps: list[tuple[str, str]], full: bool) -> None:
        for title, text in steps:
            views.print_prompt(self.console, f"{metric_id} · {title}", views.prompt_text(text, full))

    def print_custom_prompt(self, metric_id: str, full: bool = False) -> None:
        """Print the prompt in effect (custom, domain or built-in).

        Input slots such as ``{query}`` are left as placeholders. Shows a
        shortened view unless ``full`` is set.
        """
        template = self.custom_template(metric_id)
        kind = t("prompt.custom") if template else t("prompt.default")
        self.print_steps(metric_id, [(kind, preview(metric_id, self.current_template(metric_id)))], full)
        if template:
            self.console.print(Text.assemble((t("prompt.file") + " ", banner.MUTED), views.path_link(self.prompt_paths[metric_id])))

    def edit_prompt(self, metric_id: str) -> None:
        """Have the domain model revise the prompt from a request, then save and use the revision.

        Requests accumulate in the prompt file in the order they were made.
        """
        from chaejeom.cli.picker import ask_value

        self.warn_domain_model()
        request = ask_value(t("prompt.edit_ask", metric=metric_id), "", t("prompt.edit_hint"))
        if not request:
            self.info(t("cancelled"))
            return
        path = self.prompt_paths.get(metric_id)
        current = load_prompt(Path(path).expanduser(), metric_id) if path else PromptFile(metric=metric_id, template=self.current_template(metric_id))
        self.info(t("prompt.using_model", model=self.config.domain_model.model))
        try:
            # New client per asyncio.run, which starts a new event loop each time.
            revision = asyncio.run(revise(self.config.create_domain_llm(), metric_id, current.template, request))
        except PromptRevisionError:
            self.error(t("prompt.failed"))
            return
        updated = PromptFile(metric=metric_id, requests=[*current.requests, request], template=revision.template)
        saved = save_prompt(updated, Path(path).expanduser() if path else default_path(metric_id))
        self.prompt_paths[metric_id] = str(saved)
        self.print_custom_prompt(metric_id)
        if revision.summary:
            self.info(t("prompt.changes", summary=revision.summary))
        self.console.print(Text.assemble((t("prompt.saved") + " ", banner.MUTED), views.path_link(saved)))
        self.info(t("prompt.applies", metric=metric_id))

    def use_prompt(self, metric_id: str, path: str, label: str) -> None:
        """Validate a prompt file and use it for the metric."""
        load_prompt(Path(path).expanduser(), metric_id)
        self.prompt_paths[metric_id] = path
        self.console.print(Text.assemble((label + " ", banner.MUTED), views.path_link(path)))
        self.info(t("prompt.applies", metric=metric_id))
