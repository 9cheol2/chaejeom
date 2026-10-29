"""Custom chaejeom.* judge prompts revised to a user's request.

Created with ``/prompt`` and applied through a metric's ``prompt`` option. Each YAML file holds
the user's requests and the revised template. Upstream (RAGAS, DeepEval, TruLens) metrics are
kept as ported and cannot be customized.

Requests are applied freely; only what the code needs to parse results is enforced: the same
placeholders, an unchanged "[평가 지표]" line and "[출력 형식]" block, and a formattable template.
"""

import string
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chaejeom.customize import prompts
from chaejeom.llm.base import LLMClient
from chaejeom.metrics.chaejeom.prompts import TEMPLATES
from chaejeom.schema import Cost

MAX_ATTEMPTS = 3


class PromptFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    requests: list[str] = Field(default_factory=list)
    template: str


class Revision(BaseModel):
    template: str
    summary: str = ""


class PromptRevisionError(Exception):
    """Raised when no revision preserved the metric definition and output format."""


def is_editable(metric_id: str) -> bool:
    return metric_id in TEMPLATES


def default_path(metric_id: str) -> Path:
    return Path("prompts") / f"{metric_id}.yaml"


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}


def _block(template: str, title: str) -> str:
    """Return the section starting at ``title`` (e.g. "[출력 형식]") up to the next blank line."""
    start = template.index(title)
    end = template.find("\n\n", start)
    return template[start:] if end == -1 else template[start:end]


def _definition(template: str) -> str:
    return next(line for line in template.splitlines() if line.startswith("[평가 지표]"))


def check_template(metric_id: str, template: str) -> list[str]:
    """Check a custom template against the metric's default template.

    The placeholders, the "[평가 지표]" line, and the "[출력 형식]" block must match.

    Returns:
        A list of problems; empty if the template is valid.
    """
    default = TEMPLATES[metric_id]
    problems = []
    try:
        fields = _fields(template)
    except ValueError as e:
        return [f"중괄호가 짝이 맞지 않습니다 ({e}). 중괄호 문자는 두 겹으로 써야 합니다."]
    if missing := sorted(_fields(default) - fields):
        problems.append(f"자리 표시가 빠졌습니다: {', '.join('{' + m + '}' for m in missing)}")
    if extra := sorted(fields - _fields(default)):
        problems.append(f"없던 자리 표시가 생겼습니다: {', '.join('{' + e + '}' for e in extra)}")
    if _definition(default) not in template:
        problems.append("[평가 지표] 줄이 바뀌었습니다.")
    if _block(default, "[출력 형식]") not in template:
        problems.append("[출력 형식] 부분이 바뀌었습니다.")
    return problems


def load_prompt(path: str | Path, metric_id: str | None = None) -> PromptFile:
    """Load and validate a custom prompt file.

    Raises:
        ValueError: If the metric is not customizable, does not match ``metric_id``, or the
            template fails :func:`check_template`.
    """
    data = PromptFile.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    if not is_editable(data.metric):
        raise ValueError(f"{path}: 수정본을 쓸 수 있는 지표가 아닙니다: {data.metric}")
    if metric_id is not None and data.metric != metric_id:
        raise ValueError(f"{path}: {data.metric} 지표의 수정본입니다. {metric_id} 지표에는 쓸 수 없습니다.")
    if problems := check_template(data.metric, data.template):
        raise ValueError(f"{path}: 수정본 프롬프트를 쓸 수 없습니다. " + " ".join(problems))
    return data


class _Dumper(yaml.SafeDumper):
    """YAML dumper that writes multi-line strings as block scalars (``|``) so templates stay hand-editable."""


_Dumper.add_representer(
    str, lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)
)


def save_prompt(prompt: PromptFile, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(prompt.model_dump(), Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(text, encoding="utf-8")
    return path


async def revise(llm: LLMClient, metric_id: str, template: str, request: str, cost: Cost | None = None) -> Revision:
    """Ask the LLM to revise ``template`` per ``request``.

    Violations found by :func:`check_template` are fed back and the revision retried, up to
    ``MAX_ATTEMPTS`` attempts in total.

    Raises:
        PromptRevisionError: If every attempt violates the constraints.
    """
    base = prompts.revise(metric_id, template, request)
    text = base
    for _ in range(MAX_ATTEMPTS):
        revision = await llm.generate(text, Revision, cost=cost)
        problems = check_template(metric_id, revision.template)
        if not problems:
            return revision
        text = base + prompts.REVISE_RETRY.format(problems=" ".join(problems))
    raise PromptRevisionError(" ".join(problems))
