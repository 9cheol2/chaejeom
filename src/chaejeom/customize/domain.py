"""Domain profiles that adapt the chaejeom.* judge prompts to a domain.

A profile states, in the user's words, the service and how each of the three metrics should judge in this domain,
for example which targets count as the same ("memory chips can be answered with HBM, but NAND and HBM are different
targets"). It never states what the right answer is, so judging stays reference-free: the items hold kinds of
information and judging rules, never values that could serve as answers ("the fee is 3%").

The service goes into each judge prompt's role line and a metric's rules are added word for word, after the built-in
procedure and before the output format (see :func:`chaejeom.metrics.chaejeom.prompts.with_domain`). Nothing else in
the prompt changes.

:func:`organize` maps a free-form description onto the items. It does not judge whether the description is
sufficient; the profile carries exactly the detail the user provides.
"""

import difflib
import hashlib
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chaejeom.customize import prompts
from chaejeom.llm.base import LLMClient
from chaejeom.metrics.chaejeom.prompts import TEMPLATES, with_domain
from chaejeom.schema import Cost

ITEMS = prompts.ITEM_KEYS
# The item holding each metric's judging rules; ``service`` applies to all three.
METRIC_ITEMS = {
    "chaejeom.groundedness": "groundedness",
    "chaejeom.context_relevance": "context_relevance",
    "chaejeom.answer_relevance": "answer_relevance",
}
_OLD_ITEMS = {"critical_info", "document_scope", "expected_answer"}


class DomainProfile(BaseModel):
    """Domain information for the judge prompts. Empty items leave the prompt as it is."""

    model_config = ConfigDict(extra="forbid")

    name: str
    service: str = ""
    groundedness: str = ""
    context_relevance: str = ""
    answer_relevance: str = ""

    def fingerprint(self) -> str:
        """Return a short hash recorded in results to identify the criteria used; the name is not part of them."""
        text = "\n".join(getattr(self, item) for item in ITEMS)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    def template(self, metric_id: str) -> str | None:
        """Return the metric's judge prompt template with this domain applied, or ``None`` if nothing applies."""
        rules = getattr(self, METRIC_ITEMS[metric_id])
        if not (self.service or rules):
            return None
        return with_domain(TEMPLATES[metric_id], self.service, rules)


def load_profile(path: str | Path) -> DomainProfile:
    """Load a domain profile.

    Raises:
        ValueError: If the file uses the earlier item format.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if isinstance(data, dict) and (old := sorted(_OLD_ITEMS & data.keys())):
        raise ValueError(f"{path}: 예전 형식의 도메인 파일입니다 ({', '.join(old)}). /domain 으로 다시 만드세요.")
    return DomainProfile.model_validate(data)


def save_profile(profile: DomainProfile, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = profile.model_dump()
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    return path


def changed_lines(metric_id: str, template: str) -> list[tuple[str, str]]:
    """Return the lines a template removed (``"-"``) or added (``"+"``) relative to the built-in one."""
    diff = difflib.ndiff(TEMPLATES[metric_id].splitlines(), template.splitlines())
    return [(line[0], line[2:]) for line in diff if line[:1] in "-+" and line[2:].strip()]


# Values that could serve as answers (numbers with units, dates). A safety net for values the
# model failed to remove.
_VALUE = re.compile(
    r"\d[\d,.]*\s*(?:%|퍼센트|원|만원|억|조원|달러|일|개월|년|세|회|시간|분|건|명|배)"
    r"|\d{4}\s*[-./년]\s*\d{1,2}"
)


def find_values(text: str) -> list[str]:
    return [m.group(0) for m in _VALUE.finditer(text)]


class DomainDraft(BaseModel):
    """Result of :func:`organize`.

    Attributes:
        items: Refined text per profile item.
        removed_facts: Source statements dropped because they contained answer values.
        out_of_scope: Requests the metrics do not measure (tone, length, format, ...).
    """

    name: str = ""
    items: dict[str, str] = Field(default_factory=dict)
    removed_facts: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)

    def item(self, key: str) -> str:
        return self.items.get(key) or ""

    def values(self) -> list[str]:
        """Return values still present in the items."""
        return [value for key in ITEMS for value in find_values(self.item(key))]

    def to_profile(self) -> DomainProfile:
        return DomainProfile(name=self.name or "domain", **{key: self.item(key) for key in ITEMS})


async def organize(llm: LLMClient, description: str, cost: Cost | None = None) -> DomainDraft:
    """Organize a free-form domain description into the profile items.

    If the items still contain values, the model is asked once more. Values that survive are not
    stripped, since cutting out numbers would break the sentences; they remain visible through
    ``draft.values()`` for the user to fix.
    """
    prompt = prompts.organize(description)
    draft = await llm.generate(prompt, DomainDraft, cost=cost)
    if values := draft.values():
        draft = await llm.generate(prompt + prompts.ORGANIZE_RETRY.format(values=", ".join(values)), DomainDraft, cost=cost, variant=1)
    # The model sometimes lists value-less information kinds in removed_facts; keep entries with digits.
    removed = [fact for fact in draft.removed_facts if any(ch.isdigit() for ch in fact)]
    removed.extend(value for value in values if value not in removed and value not in draft.values())
    return draft.model_copy(update={"removed_facts": removed})
