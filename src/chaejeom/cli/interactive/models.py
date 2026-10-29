"""/model, /temperature, /effort and /embedding commands."""

from rich.text import Text

from chaejeom.cli import banner
from chaejeom.cli.i18n import t
from chaejeom.config import ModelConfig
from chaejeom.defaults import DEFAULT_REASONING_EFFORT, EMBEDDING_MODELS, JUDGE_MODELS, REASONING_EFFORTS


class ModelCommands:
    def is_reasoning(self) -> bool:
        """Return whether the current judge model is a reasoning model."""
        return JUDGE_MODELS.get(self.config.judge.model, {}).get("reasoning", False)

    def judge_setting(self) -> tuple[str, str]:
        """Return the judge's sampling setting as a label/value pair, e.g. ``("effort:", "low")``."""
        options = self.config.judge_options()
        if "reasoning_effort" in options:
            return "effort:", options["reasoning_effort"]
        return "temperature:", f"{options.get('temperature', 0.0):g}"

    def judge_label(self) -> str:
        label, value = self.judge_setting()
        return f"{self.config.judge.model}   {label} {value}"

    def choose_model(self, arg: str) -> None:
        """Select the judge model, then its temperature or, for reasoning models, its reasoning effort.

        The two settings are mutually exclusive.
        """
        from chaejeom.cli.picker import pick_one

        model, _, setting = arg.partition(" ")
        setting = setting.strip()
        if not model:
            model = pick_one(t("model.select"), [(m, m) for m in JUDGE_MODELS], self.config.judge.model)
            if model is None:
                self.info(t("cancelled"))
                return
        if model not in JUDGE_MODELS:
            raise ValueError(t("model.unsupported", model=model, models=", ".join(JUDGE_MODELS)))

        if JUDGE_MODELS[model]["reasoning"]:
            effort = self._pick_effort(model, setting, DEFAULT_REASONING_EFFORT)
            if effort is None:
                self.info(t("cancelled"))
                return
            self.config.judge = ModelConfig(provider="openai", model=model, reasoning_effort=effort)
        else:
            temperature = self._pick_temperature(model, setting, 0.0)
            if temperature is None:
                self.info(t("cancelled"))
                return
            self.config.judge = ModelConfig(provider="openai", model=model, temperature=temperature)
        self._print_judge()

    def choose_temperature(self, arg: str) -> None:
        model = self.config.judge.model
        if self.is_reasoning():
            raise ValueError(t("temperature.reasoning_model", model=model))
        current = self.config.judge_options().get("temperature", 0.0)
        temperature = self._pick_temperature(model, arg, current)
        if temperature is None:
            self.info(t("cancelled"))
            return
        self.config.judge = ModelConfig(provider=self.config.judge.provider, model=model, temperature=temperature)
        self._print_judge()

    def choose_effort(self, arg: str) -> None:
        model = self.config.judge.model
        if not self.is_reasoning():
            raise ValueError(t("effort.not_reasoning_model", model=model))
        current = self.config.judge_options().get("reasoning_effort", DEFAULT_REASONING_EFFORT)
        effort = self._pick_effort(model, arg, current)
        if effort is None:
            self.info(t("cancelled"))
            return
        self.config.judge = ModelConfig(provider=self.config.judge.provider, model=model, reasoning_effort=effort)
        self._print_judge()

    def _print_judge(self) -> None:
        self.console.print(Text.assemble((t("model.set") + " ", ""), (self.judge_label(), banner.MODEL)))

    @staticmethod
    def _pick_temperature(model: str, arg: str, current: float) -> float | None:
        """Parse ``arg``, or prompt with ``current`` prefilled when it is empty; None if cancelled."""
        from chaejeom.cli.picker import ask_value

        if not arg:
            arg = ask_value(t("temperature.ask", model=model), f"{current:g}", t("temperature.hint"))
            if arg is None:
                return None
        try:
            temperature = float(arg)
        except ValueError:
            raise ValueError(t("temperature.not_number", model=model)) from None
        if not 0 <= temperature <= 2:
            raise ValueError(t("temperature.range"))
        return temperature

    @staticmethod
    def _pick_effort(model: str, arg: str, current: str) -> str | None:
        """Parse ``arg``, or prompt with ``current`` prefilled when it is empty; None if cancelled."""
        from chaejeom.cli.picker import ask_value

        if not arg:
            arg = ask_value(t("effort.ask", model=model), current, t("effort.hint"))
            if arg is None:
                return None
        arg = arg.lower()
        if arg not in REASONING_EFFORTS:
            raise ValueError(t("effort.invalid", model=model, efforts=", ".join(REASONING_EFFORTS)))
        return arg

    def choose_embedding(self, arg: str) -> None:
        from chaejeom.cli.picker import pick_one

        model = arg
        if not model:
            model = pick_one(t("embedding.select"), [(m, m) for m in EMBEDDING_MODELS], self.config.embedding.model)
            if model is None:
                self.info(t("cancelled"))
                return
        if model not in EMBEDDING_MODELS:
            raise ValueError(t("embedding.unsupported", model=model, models=", ".join(EMBEDDING_MODELS)))
        self.config.embedding = ModelConfig(provider="openai", model=model)
        self.console.print(Text.assemble((t("embedding.set") + " ", ""), (model, banner.MODEL)))
