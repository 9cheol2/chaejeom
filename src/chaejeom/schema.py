from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

Axis = Literal["groundedness", "context_relevance", "answer_relevance"]

AXIS_LABELS: dict[str, str] = {
    "groundedness": "근거성",
    "context_relevance": "문맥 관련성",
    "answer_relevance": "답변 관련성",
}

UnitType = Literal["claim", "truth", "statement", "sentence", "chunk", "generated_question", "judge"]


def _to_str(value):
    return str(value) if isinstance(value, int) else value


class Context(BaseModel):
    id: str
    text: str
    rank: int

    _coerce_id = field_validator("id", mode="before")(_to_str)


class EvalSample(BaseModel):
    """A single RAG interaction to evaluate.

    ``query``, ``contexts`` and ``answer`` are all optional: an empty field only fails the
    metrics that need it. RAGAS (``user_input``, ``retrieved_contexts``, ``response``) and
    DeepEval (``input``, ``retrieval_context``, ``actual_output``) field names are accepted.
    """

    id: str | None = None
    query: str = Field("", validation_alias=AliasChoices("query", "user_input", "input"))
    contexts: list[Context] = Field(
        default_factory=list,
        validation_alias=AliasChoices("contexts", "retrieved_contexts", "retrieval_context"),
    )
    answer: str = Field("", validation_alias=AliasChoices("answer", "response", "actual_output"))
    metadata: dict[str, Any] = Field(default_factory=dict)

    _coerce_id = field_validator("id", mode="before")(_to_str)

    @field_validator("contexts", mode="before")
    @classmethod
    def _fill_context_defaults(cls, value):
        # Accept plain strings; missing ids/ranks default to c1, c2, ... and 1, 2, ... by position.
        if not isinstance(value, list):
            return value
        items = []
        for i, item in enumerate(value, start=1):
            if isinstance(item, str):
                item = {"text": item}
            if isinstance(item, dict):
                item = {"id": f"c{i}", "rank": i} | {k: v for k, v in item.items() if v is not None}
            items.append(item)
        return items


class Source(BaseModel):
    framework: Literal["ragas", "deepeval", "trulens", "chaejeom"]
    version: str
    commit: str
    method: str


class Unit(BaseModel):
    """A single judged unit (claim, statement, chunk, ...).

    Attributes:
        verdict: Raw verdict as the upstream metric emits it (0/1, yes/no, ...).
        score: Per-unit score on the metric's native scale (e.g. TruLens 0-3, cosine similarity).
        core: chaejeom.* only. True if the unit is information the query directly asks for,
            False if it is supplementary.
    """

    type: UnitType
    text: str
    verdict: str | int | float | None = None
    score: float | None = None
    reason: str | None = None
    context_ids: list[str] = Field(default_factory=list)
    core: bool | None = None


class Cost(BaseModel):
    """LLM usage and estimated cost.

    ``llm_calls`` and token counts cover real API calls only; cached responses count as
    ``cache_hits``. ``tokens`` is input plus output. ``usd`` is an estimate from
    :mod:`chaejeom.pricing` and stays 0 for models without a known price.
    """

    llm_calls: int = 0
    tokens: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0


class MetricResult(BaseModel):
    metric_id: str
    source: Source
    axis: Axis
    run: int = 1
    score: float | None = None
    raw_score: float | None = None
    raw_scale: str | None = None
    units: list[Unit] = Field(default_factory=list)
    reason: str | None = None
    cost: Cost = Field(default_factory=Cost)
    error: str | None = None
