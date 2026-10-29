"""/run, /show and /runs commands."""

import asyncio

from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.text import Text

from chaejeom.cli import banner, views
from chaejeom.cli.folders import result_paths
from chaejeom.cli.i18n import t
from chaejeom.config import apply_domain, apply_prompts
from chaejeom.evaluate import aevaluate, needs_embeddings
from chaejeom.pricing import estimate_usd, sample_stats
from chaejeom.schema import EvalSample


class RunCommands:
    def run(self, arg: str) -> None:
        """Show the planned judgments and estimated cost, then evaluate after confirmation.

        ``/run 20`` evaluates only the first 20 samples. Ctrl+C during a run
        cancels only the run; finished verdicts stay cached, so a rerun resumes
        them at no cost.
        """
        from chaejeom.cli.picker import pick_one

        if not self.samples:
            raise ValueError(t("run.no_data"))
        if arg and (not arg.isdigit() or int(arg) < 1):
            raise ValueError(t("run.invalid_limit"))
        samples = self.samples[: int(arg)] if arg else self.samples
        if not self._domain_ready():
            return
        total = len(samples) * len(self.selected) * self.repeats
        self.info(t("run.plan", samples=len(samples), metrics=len(self.selected), runs=self.repeats, total=total))
        for metric_id, path in self.prompt_paths.items():
            if metric_id in self.selected:
                self.console.print(Text.assemble((t("prompt.in_use", metric=metric_id) + "  ", banner.MUTED), views.path_link(path)))
        for line in views.data_flow_warnings(self.config, self.selected):
            self.info(line)
        estimate = self.estimate_usd(samples)
        if estimate is not None:
            self.info(t("cost.estimate", usd=views.format_usd(estimate), model=self.config.judge.model))
        if pick_one(t("run.confirm"), [("start", t("run.start")), ("cancel", t("run.cancel"))]) != "start":
            self.info(t("cancelled"))
            return
        llm = self.config.create_llm()
        embeddings = self.config.create_embeddings() if needs_embeddings(self.selected) else None

        progress = Progress(
            TextColumn(f"[bold]{t('run.progress')}"),
            BarColumn(complete_style=banner.MODEL, finished_style=views.GOOD),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        try:
            with progress:
                task = progress.add_task("evaluate", total=total)
                result = asyncio.run(
                    aevaluate(
                        samples,
                        llm,
                        metrics=[{m: o} for m, o in self.metric_options().items()],
                        embeddings=embeddings,
                        concurrency=self.config.concurrency,
                        repeats=self.repeats,
                        cache=self.config.cache_dir if self.config.cache else False,
                        on_progress=lambda done, _: progress.update(task, completed=done),
                    )
                )
        except KeyboardInterrupt:
            self.info(t("run.interrupted"))
            return
        self.result = result
        if failure := views.all_failed(result):
            self.error(t("run.all_failed", error=failure))
            return

        json_path, csv_path = result_paths(self.data_path)
        result.to_json(json_path)
        result.to_csv(csv_path)
        views.print_summary(self.console, result)
        self.console.print(
            Text.assemble((t("run.saved") + " ", banner.MUTED), views.path_link(json_path), (", ", banner.MUTED), views.path_link(csv_path))
        )
        self.info(t("run.show_hint"))

    def metric_options(self) -> dict[str, dict]:
        """Return per-metric options, adding the domain and custom prompt files to Chaejeom metrics.

        A domain file that cannot be read is left out: by then the user has chosen to run with general criteria.
        """
        domain = self.domain_path if self.domain_profile() is not None else None
        return apply_prompts(apply_domain(self.selected, domain), self.prompt_paths)

    def _domain_ready(self) -> bool:
        """Return whether the run may proceed with respect to the domain profile.

        Chaejeom metrics judge against the domain profile. If one is selected
        without a profile, ask whether to set one up now or run with general
        criteria.
        """
        from chaejeom.cli.picker import pick_one

        if self.domain_profile() is not None or not any(m.startswith("chaejeom.") for m in self.selected):
            return True
        options = [("setup", t("domain.setup_now")), ("general", t("domain.run_general")), ("cancel", t("domain.cancel_run"))]
        choice = pick_one(t("domain.missing_title"), options)
        if choice == "setup":
            self.choose_domain("")
            return bool(self.domain_path)
        if choice == "general":
            return True
        self.info(t("cancelled"))
        return False

    def estimate_usd(self, samples: list[EvalSample] | None = None) -> float | None:
        """Estimate the run cost in USD, assuming no cache hits.

        The estimate is based on average sample length, number of context
        chunks and number of answer sentences.
        """
        samples = self.samples if samples is None else samples
        if not samples:
            return None
        return estimate_usd(list(self.selected), sample_stats(samples), len(samples), self.repeats, self.config.judge.model)

    def show(self, arg: str) -> None:
        """List the samples of the last result, or show one by index or id, optionally narrowed to a framework or axis."""
        if self.result is None:
            raise ValueError(t("show.no_result"))
        parts = arg.split()
        if not parts or parts[0].lower() == "all":
            views.print_sample_list(self.console, self.result, everything=bool(parts))
            return
        views.print_sample(self.console, self.result, parts[0], parts[1] if len(parts) > 1 else None)

    def set_repeats(self, arg: str) -> None:
        """Set how many times each sample is judged per metric."""
        if not arg:
            from chaejeom.cli.picker import ask_value

            arg = ask_value(t("repeats.ask"), str(self.repeats), t("repeats.hint"))
            if arg is None:
                self.info(t("cancelled"))
                return
        if not arg.isdigit() or int(arg) < 1:
            raise ValueError(t("repeats.invalid"))
        self.repeats = int(arg)
        self.info(t("repeats.many", n=self.repeats) if self.repeats > 1 else t("repeats.one"))
