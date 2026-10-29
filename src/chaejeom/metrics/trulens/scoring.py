# Adapted from trulens 2.16.0 (MIT), commit 1f65a310cd5bdaef3ea7be76e98022f574cea39c
#   src/feedback/trulens/feedback/llm_provider.py (generate_score_and_reasons, _validate_score_range, _mean_graded_score)
#   src/feedback/trulens/feedback/generated.py (re_configured_rating, _ratings_in_range, _strip_scale_statement)
#
# Changes from upstream:
# - Upstream requests structured output (ChainOfThoughtResponse) first and, for a text
#   response, makes one more LLM call to convert it to JSON before parsing. We take a
#   text response, extract a JSON object from it (surrounding prose and code fences are
#   allowed) and use its `score` if present; criteria and supporting_evidence are
#   optional. Non-JSON responses go through upstream's text-path parser; no JSON
#   conversion call is made.
# - Without a "Score:" line upstream reads the smallest in-range number anywhere in the
#   response; we read a score only when the whole response is a single number.
# - If no score can be read from a "Score:" line or a bare-number response, we treat it
#   as unparsed (score=None) instead of raising as upstream does.
# - Scale-statement stripping also handles Korean notations: 0~3, 0～3, 0에서 3 (사이/까지),
#   0부터 3까지.
# - Upstream's failure sentinel (UNPARSABLE_SCORE = -1.0) is represented as score=None.

import json
import re
from dataclasses import dataclass

from chaejeom.llm.base import extract_json, strip_thinking

MIN_SCORE = 0
MAX_SCORE = 3

CRITERIA_FIELD = "Criteria"
SUPPORTING_EVIDENCE_FIELD = "Supporting Evidence"

PATTERN_NUMBER = re.compile(r"([+-]?[0-9]+\.[0-9]*|[1-9][0-9]*|0)")
_BARE_NUMBER = re.compile(r"\s*[+-]?[0-9]+(?:\.[0-9]*)?\s*")


class ParseError(ValueError):
    """Raised when no valid 0-3 rating can be read."""


@dataclass
class Judgment:
    """A parsed judge response.

    Attributes:
        score: Raw 0-3 rating, or None if it could not be read (upstream's UNPARSABLE_SCORE).
        criteria: The judge's restated criteria, if given.
        supporting_evidence: The judge's justification, if given.
    """

    score: float | None
    criteria: str | None = None
    supporting_evidence: str | None = None

    @property
    def normalized(self) -> float | None:
        if self.score is None:
            return None
        return (self.score - MIN_SCORE) / (MAX_SCORE - MIN_SCORE)


def _validate_score_range(rating: float) -> float:
    if not (MIN_SCORE <= rating <= MAX_SCORE):
        raise ParseError(f"{MIN_SCORE}-{MAX_SCORE} 범위의 점수를 기대했지만 {rating} 을(를) 받았습니다.")
    return rating


def _ratings_in_range(s: str) -> set[int]:
    found = set()
    for match in PATTERN_NUMBER.findall(s):
        rating = int(float(match))
        if MIN_SCORE <= rating <= MAX_SCORE:
            found.add(rating)
    return found


def _strip_scale_statement(s: str) -> str:
    lo, hi = re.escape(str(MIN_SCORE)), re.escape(str(MAX_SCORE))
    patterns = (
        rf"\b{lo}\s*(?:to|through|and|up to|\.\.\.?|[-‒-―])\s*{hi}\b",
        rf"\b{lo}\s*=",
        rf"\b{hi}\s*=",
        rf"(?<!\d){lo}\s*(?:[~～]|에서|부터)\s*{hi}(?!\d)(?:\s*(?:사이|까지))?",
    )
    for pattern in patterns:
        s = re.sub(pattern, " ", s, flags=re.IGNORECASE)
    return s


def re_configured_rating(s: str) -> int:
    """Read a 0-3 rating from `s`, taking the smallest if several in-range numbers appear.

    Scale statements such as "0 to 3" are stripped first so their bounds are not read as
    ratings.

    Raises:
        ParseError: If no in-range number is found.
    """
    if not PATTERN_NUMBER.search(s):
        raise ParseError(f"숫자를 찾지 못했습니다:\n{s}")

    without_scale = _strip_scale_statement(s)
    considered = without_scale if without_scale != s else s

    vals = _ratings_in_range(considered)
    if not vals and considered is not s:
        vals = _ratings_in_range(s)

    if not vals:
        raise ParseError(f"{MIN_SCORE}-{MAX_SCORE} 범위의 점수를 찾지 못했습니다:\n{s}")
    return min(vals)


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _json_judgment(response: str) -> Judgment | None:
    """Build a Judgment from a JSON object in the response that has a `score` key, else None.

    Raises:
        ParseError: If the score is numeric but outside 0-3.
    """
    try:
        parsed = json.loads(extract_json(strip_thinking(response)))
    except ValueError:
        return None
    if not isinstance(parsed, dict) or "score" not in parsed:
        return None
    criteria, evidence = parsed.get("criteria"), parsed.get("supporting_evidence")
    criteria = None if criteria is None else str(criteria)
    evidence = None if evidence is None else str(evidence)
    score = _number(parsed["score"])
    if score is None:
        return Judgment(None, criteria, evidence)
    return Judgment(_validate_score_range(score), criteria, evidence)


def _rating_or_none(s: str) -> int | None:
    try:
        return re_configured_rating(s)
    except ParseError:
        return None


def _score_from_lines(lines: list[str]) -> int | None:
    """Read the score from the last "Score:" line, or from a number on the line after it, as upstream does."""
    score = None
    for i, line in enumerate(lines):
        if "Score:" in line:
            if i + 1 < len(lines) and lines[i + 1].strip().replace(".", "", 1).isdigit():
                score_line = lines[i + 1]
            else:
                score_line = line
            score = _rating_or_none(score_line)
    return score


def parse_score_and_reasons(response: str) -> Judgment:
    """Parse a judge response into a `Judgment`.

    Tries a JSON object first, then upstream's "Criteria: / Supporting Evidence: / Score:"
    text format, then a bare number. Unreadable scores yield `Judgment(score=None)`.
    """
    judgment = _json_judgment(response)
    if judgment is not None:
        return judgment

    lines = response.split("\n")
    if SUPPORTING_EVIDENCE_FIELD in response:
        criteria_lines: list[str] = []
        evidence_lines: list[str] = []
        collecting_criteria = False
        collecting_evidence = False
        for line in lines:
            if f"{CRITERIA_FIELD}:" in line:
                criteria_lines.append(line.split(f"{CRITERIA_FIELD}:", 1)[1].strip())
                collecting_criteria, collecting_evidence = True, False
            elif f"{SUPPORTING_EVIDENCE_FIELD}:" in line:
                evidence_lines.append(line.split(f"{SUPPORTING_EVIDENCE_FIELD}:", 1)[1].strip())
                collecting_evidence, collecting_criteria = True, False
            elif collecting_criteria:
                criteria_lines.append(line.strip())
            elif collecting_evidence:
                evidence_lines.append(line.strip())
        criteria = "\n".join(criteria_lines).strip()
        supporting_evidence = "\n".join(evidence_lines).strip()
        return Judgment(_score_from_lines(lines), criteria, supporting_evidence)

    if any("Score:" in line for line in lines):
        return Judgment(_score_from_lines(lines))
    if _BARE_NUMBER.fullmatch(response):
        return Judgment(_rating_or_none(response))
    return Judgment(None)


def has_score(response: str) -> bool:
    """Return whether a score can be read from the response; decides whether it is cached."""
    return parse_score_and_reasons(response).score is not None


def mean_graded_score(judgments: list[Judgment]) -> float | None:
    """Average the scores of judgments that have one; None if none do."""
    graded = [j.score for j in judgments if j.score is not None]
    if not graded:
        return None
    return sum(graded) / len(graded)
