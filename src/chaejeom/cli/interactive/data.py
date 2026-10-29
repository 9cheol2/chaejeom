"""/data command."""

from pathlib import Path

from rich.text import Text

from chaejeom.cli import banner
from chaejeom.cli.folders import INPUT_DIR, input_files
from chaejeom.cli.i18n import t
from chaejeom.data import load_samples
from chaejeom.metrics import get_metric


class DataCommands:
    def load_data(self, arg: str) -> None:
        """Load a dataset file and warn about samples that lack fields the selected metrics need.

        Without a path, the files in the input folder are offered first.
        """
        if not arg:
            from chaejeom.cli.picker import ask_path, pick_one

            files = input_files()
            if files:
                current = str(self.data_path) if self.data_path else None
                arg = pick_one(t("data.pick", folder=INPUT_DIR), [*((str(f), f.name) for f in files), ("", t("data.other"))], current)
                if arg is None:
                    self.info(t("cancelled"))
                    return
            if not arg:
                arg = ask_path(t("data.ask"), t("data.hint"), str(self.data_path or ""))
            if not arg:
                self.info(t("cancelled"))
                return
        path = Path(arg.strip("'\"")).expanduser()
        if not path.is_file():
            raise ValueError(t("data.not_found", path=path))
        notices: list[tuple[str, str]] = []
        samples = load_samples(path, notices)
        self.samples, self.data_path = samples, path
        self.result = None
        counts = {f: sum(1 for s in samples if getattr(s, f)) for f in ("query", "contexts", "answer")}
        self.console.print(
            Text.assemble(
                (t("data.loaded") + " ", ""),
                (str(path), banner.PATH),
                (f"  {t('data.count', n=len(samples))}  ", "bold"),
                (t("data.fields", **counts), banner.MUTED),
            )
        )
        for kind, detail in notices:
            self.info(t(f"data.notice.{kind}", detail=detail))
        self._warn_missing()

    def _warn_missing(self) -> None:
        for metric_id in self.selected:
            metric = get_metric(metric_id)
            missing = [f for f in ("query", "contexts", "answer") if f in metric.requires]
            lacking = sum(1 for s in self.samples if any(not getattr(s, f) for f in missing))
            if lacking:
                self.error(t("data.missing", metric=metric_id, n=lacking))
