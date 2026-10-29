"""Shared judge-calling helpers for the Chaejeom metrics."""

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from chaejeom.customize.domain import DomainProfile, load_profile
from chaejeom.customize.prompt_file import load_prompt
from chaejeom.llm.base import LLMClient
from chaejeom.metrics.base import MetricOptions
from chaejeom.metrics.chaejeom.prompts import RETRY
from chaejeom.schema import Cost

T = TypeVar("T", bound=BaseModel)
MAX_ATTEMPTS = 2


def label(value: str) -> str:
    """Normalise a judge-written label such as ``"[c1]"`` or ``" C1 "`` to ``"c1"``."""
    return value.strip().strip("[]").strip().lower()


async def judge_all(
    llm: LLMClient,
    prompt: str,
    output_model: type[T],
    expected: list[str],
    items_of: Callable[[T], Sequence],
    cost: Cost,
) -> tuple[T, dict, list[str]]:
    """Ask the judge until every expected label is covered, retrying once with the missing labels named.

    Items from all attempts are merged by label; the first verdict for a label
    wins and labels not in ``expected`` are dropped.

    Returns:
        ``(last_output, items_by_label, still_missing_labels)``.
    """
    text, merged = prompt, {}
    for attempt in range(MAX_ATTEMPTS):
        output = await llm.generate(text, output_model, cost=cost, variant=attempt)
        for item in items_of(output):
            if label(item.id) in expected:
                merged.setdefault(label(item.id), item)
        missing = [e for e in expected if e not in merged]
        if not missing:
            break
        text = prompt + RETRY.format(missing=", ".join(missing))
    return output, merged, missing


class DomainOptions(MetricOptions):
    """Options shared by the Chaejeom metrics.

    Attributes:
        domain: Path to a domain profile YAML. The built-in prompt with the domain's service and rules inserted
            replaces the built-in one.
        prompt: Path to a custom prompt YAML made with ``/prompt``. Takes precedence over the domain's prompt.
    """

    domain: str | None = None
    prompt: str | None = None


@lru_cache(maxsize=16)
def _load_profile(path: str, modified: float) -> DomainProfile:
    return load_profile(path)


@lru_cache(maxsize=16)
def _load_template(path: str, modified: float, metric_id: str) -> str:
    return load_prompt(path, metric_id).template


def _existing(path: str, missing: str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise FileNotFoundError(f"{missing}: {resolved}")
    return resolved


def template_for(options: DomainOptions, metric_id: str) -> str | None:
    """Return the judge prompt template to use: the custom prompt, else the domain's, else ``None`` (built-in).

    File mtimes are part of the cache keys, so edits are picked up without a restart.
    """
    if options.prompt:
        path = _existing(options.prompt, "수정본 프롬프트 파일을 찾을 수 없습니다")
        return _load_template(str(path), path.stat().st_mtime, metric_id)
    if options.domain:
        path = _existing(options.domain, "도메인 정보 파일을 찾을 수 없습니다")
        return _load_profile(str(path), path.stat().st_mtime).template(metric_id)
    return None
