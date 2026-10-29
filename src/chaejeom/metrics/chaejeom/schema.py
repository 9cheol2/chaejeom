from typing import Literal

from pydantic import BaseModel, Field


class JudgedStatement(BaseModel):
    statement: str
    core: bool
    # True for statements claiming the asked-for information is not in the sources.
    absence: bool = False
    verdict: Literal["supported", "unsupported", "contradicted"]
    context_id: str = ""
    quote: str = ""
    reason: str = ""


class JudgedSentence(BaseModel):
    id: str
    statements: list[JudgedStatement] = Field(default_factory=list)


class GroundednessOutput(BaseModel):
    sentences: list[JudgedSentence] = Field(default_factory=list)


class JudgedChunk(BaseModel):
    id: str
    about_target: bool
    has_answer: bool
    reason: str = ""


class ContextRelevanceOutput(BaseModel):
    question_target: str = ""
    chunks: list[JudgedChunk] = Field(default_factory=list)


class AnswerRelevanceOutput(BaseModel):
    question_target: str = ""
    answer_target: str = ""
    declines_missing: bool = False
    # The answer sentence that says so; declines_missing counts only if it is really in the answer.
    declines_quote: str = ""
    evasive: bool
    same_target: bool
    discusses_asked: bool
    answers_directly: bool
    irrelevant_parts: list[str] = Field(default_factory=list)
    reason: str = ""
