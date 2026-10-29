import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from chaejeom.cache import DEFAULT_CACHE_DIR
from chaejeom.defaults import (
    DEFAULT_DOMAIN_MODEL,
    DEFAULT_EMBEDDING,
    DEFAULT_JUDGE,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_RUNS,
    JUDGE_MODELS,
)
from chaejeom.embeddings import EmbeddingClient, create_embeddings
from chaejeom.llm import LLMClient, Provider, create_llm


class ModelConfig(BaseModel):
    """Model selection. Extra keys (``base_url``, ``temperature``, ...) are passed through to the client."""

    model_config = ConfigDict(extra="allow")

    provider: Provider
    model: str

    @property
    def options(self) -> dict:
        return dict(self.model_extra or {})


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: ModelConfig = Field(default_factory=lambda: ModelConfig(**DEFAULT_JUDGE))
    embedding: ModelConfig = Field(default_factory=lambda: ModelConfig(**DEFAULT_EMBEDDING))
    domain_model: ModelConfig = Field(default_factory=lambda: ModelConfig(**DEFAULT_DOMAIN_MODEL))
    metrics: dict[str, list[str | dict[str, dict | None]] | str] | list[str | dict[str, dict | None]] | None = None
    axis: str | list[str] | None = None
    preset: str | None = None
    concurrency: int = Field(default=4, ge=1)
    # `repeats` is accepted as a legacy alias.
    runs: int = Field(default=DEFAULT_RUNS, ge=1, validation_alias=AliasChoices("runs", "repeats"))
    cache: bool = True
    cache_dir: str = DEFAULT_CACHE_DIR
    language: Literal["en", "ko"] = "en"
    domain: str | None = None
    prompts: dict[str, str] = Field(default_factory=dict)

    def judge_options(self) -> dict:
        return model_options(self.judge)

    def create_llm(self) -> LLMClient:
        return create_llm(self.judge.provider, self.judge.model, **self.judge_options())

    def create_domain_llm(self) -> LLMClient:
        """Create the model that organizes domain profiles, configured separately from the judge."""
        return create_llm(self.domain_model.provider, self.domain_model.model, **model_options(self.domain_model))

    def create_embeddings(self) -> EmbeddingClient:
        return create_embeddings(self.embedding.provider, self.embedding.model, **self.embedding.options)


def model_options(model: ModelConfig) -> dict:
    """Return client options, defaulting ``reasoning_effort`` for reasoning models that set no sampling option."""
    options = model.options
    reasoning = JUDGE_MODELS.get(model.model, {}).get("reasoning", False)
    if reasoning and not {"temperature", "reasoning_effort"} & options.keys():
        options["reasoning_effort"] = DEFAULT_REASONING_EFFORT
    return options


def apply_domain(selected: dict[str, dict], domain: str | None) -> dict[str, dict]:
    """Add the domain profile path to every chaejeom.* metric; an explicit per-metric ``domain`` wins."""
    if not domain:
        return selected
    return {m: {"domain": domain, **o} if m.startswith("chaejeom.") else o for m, o in selected.items()}


def apply_prompts(selected: dict[str, dict], prompts: dict[str, str]) -> dict[str, dict]:
    """Add custom prompt files (made with ``/prompt``) to their metrics; an explicit per-metric ``prompt`` wins."""
    if not prompts:
        return selected
    return {m: {"prompt": prompts[m], **o} if m in prompts else o for m, o in selected.items()}


def load_config(path: str | Path) -> EvalConfig:
    with open(path, encoding="utf-8") as f:
        return EvalConfig.model_validate(yaml.safe_load(f) or {})


def load_dotenv(path: str | Path = ".env") -> None:
    """Load ``KEY=VALUE`` lines from a .env file into ``os.environ`` without overriding existing variables."""
    path = Path(path)
    if not path.is_file():
        return
    # utf-8-sig strips the BOM Windows Notepad adds, which would otherwise corrupt the first key.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if value[:1] not in ("'", '"') and " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key.strip(), value.strip("'\""))
