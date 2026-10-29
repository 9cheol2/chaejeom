"""Deterministic level rules that turn judge marks into scores of 0, 0.25, 0.5, 0.75 or 1.0.

Judges asked to pick a level directly waver between neighbouring levels
(CheckEval), so the judge only marks checkable items (statements, chunks, how
the answer responds) and the code maps identical marks to identical scores. A domain profile changes
how the judge marks, never these rules.

Each ``*_level`` function returns ``(score, rule)``, where ``rule`` explains the
score in Korean for the result.
"""

import re
import unicodedata
from difflib import SequenceMatcher

RAW_SCALE = "0, 0.25, 0.5, 0.75, 1.0"

SUPPORTED, UNSUPPORTED, CONTRADICTED = "supported", "unsupported", "contradicted"
RELEVANT, PARTIAL, IRRELEVANT = "relevant", "partial", "irrelevant"
DIRECT, INDIRECT, OTHER_ASPECT, OFF_TOPIC, EVASIVE = "direct", "indirect", "other_aspect", "off_topic", "evasive"
DECLINED = "declined"


def groundedness_level(statements: list[tuple[str, bool]]) -> tuple[float | None, str]:
    """Score groundedness from ``(verdict, core)`` per statement.

    Levels:
        1.0: every statement is supported.
        0.0: no core statement is supported.
        0.25: a core statement is supported, but some statement is contradicted.
        0.5: a core statement is supported, but another core one is unsupported.
        0.75: all core statements are supported; only peripheral ones are unsupported.

    If no statement is marked core, all are treated as core. An answer with no
    factual statements is not scored (``None``).
    """
    if not statements:
        return None, "판단할 사실 진술이 없어 점수를 매기지 않았습니다."
    if not any(core for _, core in statements):
        statements = [(verdict, True) for verdict, _ in statements]
    verdicts = [v for v, _ in statements]
    core = [v for v, is_core in statements if is_core]
    if all(v == SUPPORTED for v in verdicts):
        return 1.0, "모든 진술이 문맥으로 뒷받침됩니다."
    if SUPPORTED not in core:
        return 0.0, "질문이 묻는 것에 대해 문맥으로 뒷받침되는 진술이 없습니다."
    if CONTRADICTED in verdicts:
        return 0.25, "뒷받침되는 핵심 진술이 있지만, 문맥과 어긋나는 진술이 있습니다."
    if UNSUPPORTED in core:
        return 0.5, "뒷받침되는 핵심 진술이 있지만, 문맥에 없는 핵심 진술도 있습니다."
    return 0.75, "핵심 진술은 모두 뒷받침되지만, 문맥에 없는 부수 진술이 있습니다."


def context_relevance_level(verdicts: list[str]) -> tuple[float, str]:
    """Score context relevance from one ``relevant``/``partial``/``irrelevant`` verdict per chunk.

    Whether any chunk holds the answer sets the band; the share of irrelevant
    chunks sets the level within it:
        1.0: an answer chunk and no irrelevant chunks.
        0.75: an answer chunk and fewer than half irrelevant.
        0.5: an answer chunk but at least half irrelevant.
        0.25: no answer chunk, but some chunk is about the question's target.
        0.0: nothing relevant.

    ``partial`` (same target, no answer) counts as neither answer nor noise.
    """
    relevant, partial, irrelevant = (verdicts.count(v) for v in (RELEVANT, PARTIAL, IRRELEVANT))
    if relevant:
        if irrelevant == 0:
            return 1.0, "답을 담은 조각이 있고, 관련 없는 조각이 없습니다."
        if irrelevant * 2 < len(verdicts):
            return 0.75, "답을 담은 조각이 있고, 관련 없는 조각이 절반 미만입니다."
        return 0.5, "답을 담은 조각이 있지만, 관련 없는 조각이 절반 이상입니다."
    if partial:
        return 0.25, "질문의 대상을 다루는 조각은 있지만, 답을 담은 조각이 없습니다."
    return 0.0, "질문과 관련 있는 문맥 조각이 없습니다."


def chunk_verdict(about_target: bool, has_answer: bool) -> str:
    """Map a chunk's yes/no marks to a verdict; a chunk off the question's target is irrelevant even if it has an answer."""
    if not about_target:
        return IRRELEVANT
    return RELEVANT if has_answer else PARTIAL


def answer_kind(evasive: bool, same_target: bool, discusses_asked: bool, answers_directly: bool, declines_missing: bool = False) -> str:
    """Classify how the answer responds from the judge's yes/no marks; earlier checks win.

    An answer stating that the information is missing from the sources is
    ``declined``, distinct from ``evasive``.
    """
    if declines_missing:
        return DECLINED
    if evasive:
        return EVASIVE
    if not same_target:
        return OFF_TOPIC
    if answers_directly:
        return DIRECT
    return INDIRECT if discusses_asked else OTHER_ASPECT


def answer_relevance_level(kind: str, has_irrelevant_parts: bool) -> tuple[float | None, str]:
    """Score answer relevance from the answer kind and whether it has irrelevant parts.

    Levels: direct 1.0 (0.75 with irrelevant parts), indirect 0.5, other aspect
    0.25, off-topic or evasive 0.0. A declined answer is not scored (``None``);
    whether the information really was missing is judged by groundedness, which
    sees the contexts.
    """
    if kind == DECLINED:
        return None, "질문이 묻는 정보가 자료에 없다고 밝혀 답변 관련성은 매기지 않습니다. 이 판단이 맞았는지는 근거성에서 봅니다."
    if kind == DIRECT:
        if has_irrelevant_parts:
            return 0.75, "질문에 직접 답하지만, 질문과 관계없는 내용이 덧붙어 있습니다."
        return 1.0, "질문이 묻는 것에 직접 답하고, 관계없는 내용이 없습니다."
    if kind == INDIRECT:
        return 0.5, "주제는 맞지만, 묻는 것을 직접 답하지 않고 일반적인 설명이나 조건만 말합니다."
    if kind == OTHER_ASPECT:
        return 0.25, "같은 주제의 다른 것을 답합니다."
    if kind == OFF_TOPIC:
        return 0.0, "질문과 다른 주제를 답합니다."
    return 0.0, "질문에 답하지 않고 답을 피합니다."


# Quote normalisation: judges often copy full-width digits, middle dots, quotes and tildes as look-alike characters.
_SAME = str.maketrans({"ㆍ": "·", "•": "·", "∙": "·", "‧": "·", "〜": "~", "∼": "~", "‐": "-", "–": "-", "—": "-"})
_DROP = re.compile(r"[\s\"'“”‘’「」『』〈〉《》]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MIN_QUOTE_CHARS = 5
# Korean negation that a "the materials do not have it" statement always contains.
SAYS_MISSING = re.compile(r"없|않|못")
MIN_QUOTE_COVERAGE = 0.9


def _squeeze(text: str) -> str:
    # Translate before NFKC, which would otherwise turn U+318D into a different character.
    return _DROP.sub("", unicodedata.normalize("NFKC", text.translate(_SAME)))


def find_quote(quote: str, texts: dict[str, str], preferred: str | None = None) -> str | None:
    """Return the id of the text ``quote`` comes from, or ``None``.

    Whitespace, quotation marks and full-/half-width differences are ignored.
    ``preferred`` (the id the judge cited) is checked first. An exact match in
    any text wins; otherwise a near match (see ``_nearly_contains``) is accepted.
    Quotes shorter than ``MIN_QUOTE_CHARS`` after normalisation are rejected,
    since they would match almost anywhere.
    """
    needle = _squeeze(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return None
    ids = ([preferred] if preferred in texts else []) + [i for i in texts if i != preferred]
    hays = {i: _squeeze(texts[i]) for i in ids}
    exact = next((i for i in ids if needle in hays[i]), None)
    return exact or next((i for i in ids if _nearly_contains(needle, hays[i])), None)


def _nearly_contains(needle: str, hay: str) -> bool:
    """Whether ``needle`` is a lightly edited copy of a passage in ``hay``.

    Judges rewrite connective endings when quoting Korean ("있으며," becomes
    "있다") and skip the middle of long sentences, so a correct quote is often
    not an exact substring. Accept it when at most two in-order pieces of one
    text, each at least ``MIN_QUOTE_CHARS`` long, cover ``MIN_QUOTE_COVERAGE``
    of the quote and every number in the quote appears in that text, so a
    changed figure is still rejected.
    """
    hay_numbers = {n.replace(",", "") for n in _NUMBER.findall(hay)}
    if any(n.replace(",", "") not in hay_numbers for n in _NUMBER.findall(needle)):
        return False
    matcher = SequenceMatcher(None, needle, hay, autojunk=False)
    first = matcher.find_longest_match(0, len(needle), 0, len(hay))
    if first.size < MIN_QUOTE_CHARS:
        return False
    before = matcher.find_longest_match(0, first.a, 0, first.b)
    after = matcher.find_longest_match(first.a + first.size, len(needle), first.b + first.size, len(hay))
    second = max((m.size for m in (before, after) if m.size >= MIN_QUOTE_CHARS), default=0)
    return (first.size + second) / len(needle) >= MIN_QUOTE_COVERAGE


def missing_numbers(statement: str, quote: str) -> list[str]:
    """Return numbers in ``statement`` that do not appear in ``quote`` (thousands separators ignored)."""
    quoted = {n.replace(",", "") for n in _NUMBER.findall(_squeeze(quote))}
    return [n for n in _NUMBER.findall(_squeeze(statement)) if n.replace(",", "") not in quoted]
