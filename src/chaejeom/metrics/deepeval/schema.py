# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/{faithfulness,answer_relevancy,contextual_relevancy}/schema.py
#
# Changes from upstream:
# - `verdicts` is required and the verdict vocabulary is validated, matching the
#   structured-output path upstream takes with its default model (gpt-4o-mini).
# - Verdicts are normalized with `normalize_qag_verdict` instead of a `Literal`. Values
#   outside the allowed vocabulary raise a validation error, which hands the response to
#   the LLM client's JSON-format retry. Replies like "No, it's off-topic" and the legacy
#   "idk" are still accepted.

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from chaejeom.metrics.deepeval.qag import YES_NO, YES_NO_BORDERLINE, normalize_qag_verdict


class Truths(BaseModel):
    truths: list[str]


class Claims(BaseModel):
    claims: list[str]


class Statements(BaseModel):
    statements: list[str]


class ScoreReason(BaseModel):
    reason: str


class RawVerdict(BaseModel):
    """A faithfulness or answer_relevancy verdict: yes, no or borderline."""

    model_config = ConfigDict(extra="allow")
    allowed: ClassVar[tuple[str, ...]] = YES_NO_BORDERLINE

    verdict: str
    reason: str | None = Field(default=None)

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, value: object) -> str:
        verdict = normalize_qag_verdict(value, cls.allowed)
        if verdict is None:
            raise ValueError(f"verdict 는 {', '.join(cls.allowed)} 중 하나여야 합니다. 받은 값: {value!r}")
        return verdict


class RawVerdicts(BaseModel):
    verdicts: list[RawVerdict]


class RawStatementVerdict(RawVerdict):
    """A contextual_relevancy verdict: yes or no."""

    allowed: ClassVar[tuple[str, ...]] = YES_NO

    statement: str


class RawStatementVerdicts(BaseModel):
    verdicts: list[RawStatementVerdict]
