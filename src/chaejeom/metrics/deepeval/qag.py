# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/base_metric.py (Verdict, YES_NO, YES_NO_BORDERLINE, LEGACY_VERDICT_ALIASES)
#   deepeval/metrics/utils/qag.py (normalize_qag_verdict, score_qag_verdicts)
#
# Changes from upstream:
# - Plain string constants instead of the `Verdict` enum.
# - strict_mode handling is not ported; Chaejeom uses neither threshold nor strict_mode.
# - If verdicts were returned but all were dropped as out of vocabulary, raise instead of
#   returning `empty_score`. `empty_score` applies only when there were no verdicts at all.

import re
from typing import Any

YES = "yes"
NO = "no"
BORDERLINE = "borderline"

YES_NO: tuple[str, ...] = (YES, NO)
YES_NO_BORDERLINE: tuple[str, ...] = (YES, NO, BORDERLINE)

# Older upstream prompts used "idk" instead of "borderline".
LEGACY_VERDICT_ALIASES: dict[str, str] = {"idk": BORDERLINE}


def normalize_qag_verdict(raw: Any, allowed: tuple[str, ...] = YES_NO) -> str | None:
    """Normalize a raw verdict to one of `allowed`.

    Only the leading word of the stripped, lowercased value is read, so replies such as
    "No, it's off-topic" are accepted.

    Returns:
        The normalized verdict, or None if it is outside `allowed` (excluded from scoring).
    """
    match = re.match(r"[a-z]+", str(raw if raw is not None else "").strip().lower())
    leading = match.group(0) if match else ""
    verdict = LEGACY_VERDICT_ALIASES.get(leading, leading)
    if verdict not in YES_NO_BORDERLINE:
        return None
    return verdict if verdict in allowed else None


def score_qag_verdicts(verdicts: list[str | None], *, passing: tuple[str, ...], empty_score: float = 1) -> float:
    """Return the fraction of verdicts that are in `passing`, ignoring None (dropped) entries.

    Returns `empty_score` when `verdicts` is empty.

    Raises:
        ValueError: If `verdicts` is non-empty but every entry was dropped.
    """
    kept = [v for v in verdicts if v is not None]
    if len(kept) == 0:
        if verdicts:
            raise ValueError(f"판정 {len(verdicts)}개가 모두 허용 어휘 밖이라 점수를 계산할 수 없습니다.")
        return empty_score
    passed = sum(1 for v in kept if normalize_qag_verdict(v, passing) is not None)
    return passed / len(kept)
