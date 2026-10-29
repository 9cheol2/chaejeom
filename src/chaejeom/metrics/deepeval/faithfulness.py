# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/faithfulness/faithfulness.py (a_measure, eval_mode="llm" path)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema; extracted truths and
#   per-claim verdicts are recorded as units.
# - threshold, strict_mode, system_one and multimodal inputs are not ported.
# - With include_reason=False upstream leaves reason as None; we set a Korean summary
#   sentence instead. The score is unaffected.
# - As on upstream's structured-output path, `verdicts` is required and out-of-vocabulary
#   verdicts are treated as format errors (see schema.py).
# - The LLM client re-requests responses that are not valid JSON for the schema. Upstream
#   relies on structured output and has no such retry.

import asyncio

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.deepeval.prompts import faithfulness as prompts
from chaejeom.metrics.deepeval.qag import (
    BORDERLINE,
    NO,
    YES,
    YES_NO_BORDERLINE,
    normalize_qag_verdict,
    score_qag_verdicts,
)
from chaejeom.metrics.deepeval.schema import Claims, RawVerdicts, ScoreReason, Truths
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="deepeval",
    version="4.3.1",
    commit="29dcf5f24397715a60348c1e41e7d416a3b2d6c8",
    method="문맥에서 사실, 답변에서 주장을 추출하고, 주장마다 문맥과 모순되는지 yes/no/borderline 로 판정한 뒤 통과 비율을 계산",
)


class FaithfulnessOptions(MetricOptions):
    include_reason: bool = True  # False: summarize verdict counts instead of an extra LLM call
    penalize_ambiguous_claims: bool = False  # count "borderline" claims as failing
    truths_extraction_limit: int | None = None  # top-N truths per document; None for all, negatives clamp to 0


@register
class Faithfulness(Metric):
    """DeepEval faithfulness: the share of answer claims that do not contradict the context."""

    metric_id = "deepeval.faithfulness"
    axis = "groundedness"
    source = SOURCE
    requires = frozenset({"query", "answer", "contexts"})
    Options = FaithfulnessOptions

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        for field in ("query", "answer", "contexts"):
            if not getattr(sample, field):
                raise ValueError(f"{field} 가 비어 있습니다.")

        cost = Cost()
        retrieval_context = [c.text for c in sample.contexts]
        truths, claims = await asyncio.gather(
            self._generate_truths(retrieval_context, cost),
            self._generate_claims(sample.answer, cost),
        )
        raw_verdicts = await self._generate_verdicts(claims, truths, cost)
        verdicts = [normalize_qag_verdict(v.verdict, YES_NO_BORDERLINE) for v in raw_verdicts.verdicts]
        score = self._calculate_score(verdicts)

        if self.options.include_reason:
            reason = await self._generate_reason(raw_verdicts, verdicts, score, cost)
        else:
            reason = self._summary(verdicts)

        units = [Unit(type="truth", text=t) for t in truths]
        for i, claim in enumerate(claims):
            raw = raw_verdicts.verdicts[i] if i < len(raw_verdicts.verdicts) else None
            units.append(
                Unit(
                    type="claim",
                    text=claim,
                    verdict=verdicts[i] if raw is not None else None,
                    reason=raw.reason if raw is not None else None,
                )
            )

        passing = "yes" if self.options.penalize_ambiguous_claims else "yes, borderline"
        return self.result(
            score=score,
            raw_score=score,
            raw_scale=f"0~1 (판정된 주장 중 통과({passing})의 비율)",
            units=units,
            reason=reason,
            cost=cost,
        )

    async def _generate_truths(self, retrieval_context: list[str], cost: Cost) -> list[str]:
        prompt = prompts.generate_truths("\n\n".join(retrieval_context), self._truths_limit())
        result = await self.llm.generate(prompt, Truths, cost=cost)
        return result.truths

    async def _generate_claims(self, actual_output: str, cost: Cost) -> list[str]:
        result = await self.llm.generate(prompts.generate_claims(actual_output), Claims, cost=cost)
        return result.claims

    async def _generate_verdicts(self, claims: list[str], truths: list[str], cost: Cost) -> RawVerdicts:
        if len(claims) == 0:
            return RawVerdicts(verdicts=[])
        prompt = prompts.generate_verdicts(claims, "\n\n".join(truths))
        return await self.llm.generate(prompt, RawVerdicts, cost=cost)

    async def _generate_reason(
        self, raw_verdicts: RawVerdicts, verdicts: list[str | None], score: float, cost: Cost
    ) -> str:
        contradictions: list[str | None] = []
        for raw, verdict in zip(raw_verdicts.verdicts, verdicts):
            if verdict == NO:
                contradictions.append(raw.reason)
            if verdict == BORDERLINE and self.options.penalize_ambiguous_claims:
                contradictions.append(f"(애매함) {raw.reason}")
        prompt = prompts.generate_reason(contradictions, format(score, ".2f"))
        result = await self.llm.generate(prompt, ScoreReason, cost=cost)
        return result.reason

    def _truths_limit(self) -> int | None:
        limit = self.options.truths_extraction_limit
        return max(limit, 0) if limit is not None else None

    def _calculate_score(self, verdicts: list[str | None]) -> float:
        passing = (YES,) if self.options.penalize_ambiguous_claims else (YES, BORDERLINE)
        return score_qag_verdicts(verdicts, passing=passing)

    @staticmethod
    def _summary(verdicts: list[str | None]) -> str:
        counts = {v: sum(1 for x in verdicts if x == v) for v in (YES, BORDERLINE, NO)}
        judged = sum(counts.values())
        return f"판정된 주장 {judged}개 중 yes {counts[YES]}개, borderline {counts[BORDERLINE]}개, no {counts[NO]}개입니다."
