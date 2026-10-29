# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/contextual_relevancy/contextual_relevancy.py (a_measure, eval_mode="llm" path)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema; per-context statement
#   verdicts are recorded as units, with the source context id in `context_ids`.
# - threshold, strict_mode, system_one and multimodal inputs are not ported.
# - With include_reason=False upstream leaves reason as None; we set a Korean summary
#   sentence instead. The score is unaffected.
# - As on upstream's structured-output path, `verdicts` is required and out-of-vocabulary
#   verdicts are treated as format errors (see schema.py).
# - The LLM client re-requests responses that are not valid JSON for the schema. Upstream
#   relies on structured output and has no such retry.

import asyncio

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.deepeval.prompts import contextual_relevancy as prompts
from chaejeom.metrics.deepeval.qag import NO, YES, YES_NO, normalize_qag_verdict, score_qag_verdicts
from chaejeom.metrics.deepeval.schema import RawStatementVerdicts, ScoreReason
from chaejeom.schema import Context, Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="deepeval",
    version="4.3.1",
    commit="29dcf5f24397715a60348c1e41e7d416a3b2d6c8",
    method="문맥 조각마다 진술을 추출해 입력과 관련 있는지 yes/no 로 판정하고, 모든 진술 중 yes 의 비율을 계산",
)


class ContextualRelevancyOptions(MetricOptions):
    include_reason: bool = True  # False: summarize verdict counts instead of an extra LLM call


@register
class ContextualRelevancy(Metric):
    """DeepEval contextual relevancy: the share of context statements relevant to the query."""

    metric_id = "deepeval.contextual_relevancy"
    axis = "context_relevance"
    source = SOURCE
    requires = frozenset({"query", "contexts"})
    Options = ContextualRelevancyOptions

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        for field in ("query", "contexts"):
            if not getattr(sample, field):
                raise ValueError(f"{field} 가 비어 있습니다.")

        cost = Cost()
        verdicts_list = await asyncio.gather(
            *(self._generate_verdicts(sample.query, context, cost) for context in sample.contexts)
        )

        units: list[Unit] = []
        judged: list[tuple[str, str, str | None]] = []  # (verdict, statement, reason); out-of-vocabulary verdicts excluded
        for context, raw_verdicts in zip(sample.contexts, verdicts_list):
            for raw in raw_verdicts.verdicts:
                verdict = normalize_qag_verdict(raw.verdict, YES_NO)
                units.append(
                    Unit(
                        type="statement",
                        text=raw.statement,
                        verdict=verdict,
                        reason=raw.reason,
                        context_ids=[context.id],
                    )
                )
                if verdict is not None:
                    judged.append((verdict, raw.statement, raw.reason))

        score = score_qag_verdicts([v for v, _, _ in judged], passing=(YES,), empty_score=0)

        if self.options.include_reason:
            reason = await self._generate_reason(sample.query, judged, score, cost)
        else:
            relevant = sum(1 for v, _, _ in judged if v == YES)
            reason = f"문맥에서 판정된 진술 {len(judged)}개 중 입력과 관련 있는(yes) 진술은 {relevant}개입니다."

        return self.result(
            score=score,
            raw_score=score,
            raw_scale="0~1 (모든 문맥에서 판정된 진술 중 yes 의 비율)",
            units=units,
            reason=reason,
            cost=cost,
        )

    async def _generate_verdicts(self, input: str, context: Context, cost: Cost) -> RawStatementVerdicts:
        prompt = prompts.generate_verdicts(input, context.text)
        return await self.llm.generate(prompt, RawStatementVerdicts, cost=cost)

    async def _generate_reason(
        self, input: str, judged: list[tuple[str, str, str | None]], score: float, cost: Cost
    ) -> str:
        irrelevant_statements = [reason for verdict, _, reason in judged if verdict == NO]
        relevant_statements = [statement for verdict, statement, _ in judged if verdict != NO]
        prompt = prompts.generate_reason(input, irrelevant_statements, relevant_statements, format(score, ".2f"))
        result = await self.llm.generate(prompt, ScoreReason, cost=cost)
        return result.reason
