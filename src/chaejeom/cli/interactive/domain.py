"""/domain command."""

import asyncio
from pathlib import Path

from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.i18n import t
from chaejeom.config import ModelConfig
from chaejeom.customize.domain import (
    ITEMS,
    METRIC_ITEMS,
    DomainDraft,
    DomainProfile,
    changed_lines,
    load_profile,
    organize,
    save_profile,
)
from chaejeom.defaults import JUDGE_MODELS


class DomainCommands:
    def domain_profile(self) -> DomainProfile | None:
        """Return the configured domain profile, or None if unset or unreadable."""
        if not self.domain_path:
            return None
        try:
            return load_profile(self.domain_path)
        except (OSError, ValueError):
            return None

    def domain_name(self) -> str:
        """Return the domain name for the status line.

        An unreadable domain file is reported as missing rather than shown as "none".
        """
        if not self.domain_path:
            return "none"
        profile = self.domain_profile()
        return profile.name if profile else t("domain.status_missing", path=self.domain_path)

    def choose_domain(self, arg: str) -> None:
        """Load a domain file, build one from a description, or turn the domain off.

        The domain profile only affects Chaejeom's own metrics.
        """
        from chaejeom.cli.picker import ask_path, pick_one

        if arg.lower() == "off":
            self.domain_path = None
            self.info(t("domain.cleared"))
            return
        if not arg:
            options = [("new", t("domain.new")), ("load", t("domain.load"))]
            if self.domain_path:
                options += [("show", t("domain.show")), ("off", t("domain.off"))]
            options.append(("model", f"{t('domain.model')} ({self.config.domain_model.model})"))
            choice = pick_one(t("domain.menu"), options)
            if choice is None:
                self.info(t("cancelled"))
                return
            if choice == "new":
                self.build_domain()
                return
            if choice == "show":
                self.print_domain(self.domain_profile())
                self.print_domain_changes(self.domain_profile())
                return
            if choice == "off":
                self.choose_domain("off")
                return
            if choice == "model":
                model = pick_one(t("domain.model_select"), [(m, m) for m in JUDGE_MODELS], self.config.domain_model.model)
                if model is None:
                    self.info(t("cancelled"))
                    return
                self.config.domain_model = ModelConfig(provider="openai", model=model)
                self.info(t("domain.model_set", model=model))
                return
            arg = ask_path(t("domain.load_ask"), t("domain.load_hint")) or ""
            if not arg:
                self.info(t("cancelled"))
                return
        path = Path(arg.strip("'\"")).expanduser()
        profile = load_profile(path)
        self.domain_path = str(path)
        self.print_domain(profile)
        self.info(t("domain.applies"))

    def print_domain(self, profile: DomainProfile | None, draft: DomainDraft | None = None) -> None:
        """Print the profile one item per line; with a draft, also list what was removed or ignored."""
        if profile is None:
            self.info(t("domain.not_set"))
            return
        line = Text.assemble(("domain: ", banner.LABEL), (profile.name, banner.MODEL))
        if self.domain_path and draft is None:
            line.append("  ")
            line.append(views.path_link(self.domain_path))
        self.console.print(line)
        width = max(len(item) for item in ITEMS) + 2
        for item in ITEMS:
            text = getattr(profile, item) or t("domain.empty_text")
            line = Text.assemble(("  ", ""), (f"{item:<{width}}", banner.LABEL))
            line.append(text, banner.TEXT if getattr(profile, item) else banner.MUTED)
            self.console.print(line)
        if draft is not None:
            if draft.removed_facts:
                self.info(t("domain.removed", values=", ".join(draft.removed_facts)))
            if draft.out_of_scope:
                self.info(t("domain.ignored", items=", ".join(draft.out_of_scope)))

    def print_domain_changes(self, profile: DomainProfile | None) -> None:
        """Print, per metric, the lines the domain changes in the built-in judge prompt."""
        if profile is None:
            return
        for metric_id in METRIC_ITEMS:
            template = profile.template(metric_id)
            if template is None:
                self.info(t("domain.no_changes", metric=metric_id))
                continue
            self.console.print(Text(t("domain.changes", metric=metric_id), banner.LABEL))
            for sign, line in changed_lines(metric_id, template):
                self.console.print(Text(f"  {sign} {line}", banner.RED_PEN if sign == "-" else banner.MODEL))

    def build_domain(self) -> None:
        """Organize a description into the profile items and save them after confirmation.

        The description is not checked for completeness; items it does not cover stay empty. The prompt lines the
        items change are shown before saving.
        """
        from chaejeom.cli.picker import ask_path, ask_value, pick_one

        self.warn_domain_model()
        description = ask_value(t("domain.ask"), "", t("domain.hint"))
        while True:
            if not description:
                self.info(t("cancelled"))
                return
            self.info(t("domain.using_model", model=self.config.domain_model.model))
            # Create a new client each time: asyncio.run starts a new event loop, and
            # connections bound to a previous loop cannot be reused.
            draft = asyncio.run(organize(self.config.create_domain_llm(), description))
            profile = draft.to_profile()
            self.print_domain(profile, draft)
            if not draft.values():
                break
            # Never save values that could act as answers. Stripping them would break the
            # sentences, so the user rewrites the description instead.
            self.error(t("domain.values_left", values=", ".join(draft.values())))
            if pick_one(t("domain.values_title"), [("redo", t("domain.redo")), ("discard", t("domain.discard"))]) != "redo":
                self.info(t("cancelled"))
                return
            description = ask_value(t("domain.ask"), description, t("domain.hint"))

        self.print_domain_changes(profile)

        if pick_one(t("domain.confirm"), [("save", t("domain.save")), ("discard", t("domain.discard"))]) != "save":
            self.info(t("cancelled"))
            return
        default = f"domains/{profile.name.replace(' ', '-')}.yaml"
        path = ask_path(t("domain.path_ask"), t("domain.path_hint"), default)
        if not path:
            self.info(t("cancelled"))
            return
        self.domain_path = str(save_profile(profile, Path(path).expanduser()))
        self.console.print(Text.assemble((t("domain.set", name=profile.name) + "  ", ""), views.path_link(self.domain_path)))
        self.info(t("domain.applies"))

    def warn_domain_model(self) -> None:
        """Warn when the domain model sends data to a different endpoint than the judge."""
        if views.endpoint(self.config.domain_model) != views.endpoint(self.config.judge):
            model = self.config.domain_model
            self.info(t("dataflow.domain_model", provider=views.endpoint(model), model=model.model, judge=views.endpoint(self.config.judge)))
