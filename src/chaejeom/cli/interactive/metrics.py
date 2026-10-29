"""/metrics command."""

from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.i18n import t
from chaejeom.evaluate import select_metrics
from chaejeom.metrics import get_metric


class MetricCommands:
    def choose_metrics(self, arg: str) -> None:
        """Select metrics from comma-separated patterns, or from a picker that also sets the run count."""
        if arg:
            patterns = [p.strip() for p in arg.split(",") if p.strip()]
            try:
                self.selected = select_metrics(patterns)
            except KeyError:
                raise ValueError(t("metrics.unknown", patterns=arg)) from None
        else:
            from chaejeom.cli.picker import pick_metrics

            picked = pick_metrics(set(self.selected), self.repeats)
            if picked is None:
                self.info(t("cancelled"))
                return
            chosen, repeats = picked
            if not chosen:
                raise ValueError(t("metrics.none"))
            self.selected = {m: self.selected.get(m, {}) for m in views.ordered_metrics() if m in chosen}
            self.repeats = repeats
        self.print_selected()
        if self.samples:
            self._warn_missing()

    def print_selected(self) -> None:
        """Print the selected metrics grouped by axis, followed by the run count."""
        width = max(banner.display_width(views.axis_name(axis)) for axis in views.AXES) + 2
        for axis in views.AXES:
            names = [
                f"{views.FRAMEWORK_LABELS[m.split('.', 1)[0]]} {views.METRIC_NAMES.get(m, m)}"
                for m in views.ordered_metrics()
                if m in self.selected and get_metric(m).axis == axis
            ]
            if names:
                self.console.print(Text.assemble((banner.pad(views.axis_name(axis), width), banner.ACCENT), ", ".join(names)))
        runs = t("runs.many", n=self.repeats) if self.repeats > 1 else t("runs.one")
        self.console.print(Text.assemble((banner.pad("Runs", width), banner.ACCENT), runs))
