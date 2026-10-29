# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/answer_relevancy/answer_relevancy.py (a_measure, eval_mode="llm" path)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema; per-statement verdicts
#   are recorded as units.
# - threshold, strict_mode, system_one and multimodal inputs are not ported.
# - With include_reason=False upstream leaves reason as None; we set a Korean summary
#   sentence instead. The score is unaffected.
# - As on upstream's structured-output path, `verdicts` is required and out-of-vocabulary
#   verdicts are treated as format errors (see schema.py).
# - The LLM client re-requests responses that are not valid JSON for the schema. Upstream
#   relies on structured output and has no such retry.

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.deepeval.prompts import answer_relevancy as prompts
from chaejeom.metrics.deepeval.qag import (
    BORDERLINE,
    NO,
    YES,
    YES_NO_BORDERLINE,
    normalize_qag_verdict,
    score_qag_verdicts,
)
from chaejeom.metrics.deepeval.schema import RawVerdicts, ScoreReason, Statements
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="deepeval",
    version="4.3.1",
    commit="29dcf5f24397715a60348c1e41e7d416a3b2d6c8",
    method="답변을 진술로 나누고, 진술마다 입력과 관련 있는지 yes/no/borderline 로 판정한 뒤 yes 와 borderline 의 비율을 계산",
)


class AnswerRelevancyOptions(MetricOptions):
    include_reason: bool = True  # False: summarize verdict counts instead of an extra LLM call


@register
class AnswerRelevancy(Metric):
    """DeepEval answer relevancy: the share of answer statements relevant to the query."""

    metric_id = "deepeval.answer_relevancy"
    axis = "answer_relevance"
    source = SOURCE
    requires = frozenset({"query", "answer"})
    Options = AnswerRelevancyOptions

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        for field in ("query", "answer"):
            if not getattr(sample, field):
                raise ValueError(f"{field} 가 비어 있습니다.")

        cost = Cost()
        statements = await self._generate_statements(sample.answer, cost)
        raw_verdicts = await self._generate_verdicts(sample.query, statements, cost)
        verdicts = [normalize_qag_verdict(v.verdict, YES_NO_BORDERLINE) for v in raw_verdicts.verdicts]
        score = score_qag_verdicts(verdicts, passing=(YES, BORDERLINE))

        if self.options.include_reason:
            reason = await self._generate_reason(sample.query, raw_verdicts, verdicts, score, cost)
        else:
            reason = self._summary(verdicts)

        units = []
        for i, statement in enumerate(statements):
            raw = raw_verdicts.verdicts[i] if i < len(raw_verdicts.verdicts) else None
            units.append(
                Unit(
                    type="statement",
                    text=statement,
                    verdict=verdicts[i] if raw is not None else None,
                    reason=raw.reason if raw is not None else None,
                )
            )

        return self.result(
            score=score,
            raw_score=score,
            raw_scale="0~1 (판정된 진술 중 yes, borderline 의 비율)",
            units=units,
            reason=reason,
            cost=cost,
        )

    async def _generate_statements(self, actual_output: str, cost: Cost) -> list[str]:
        result = await self.llm.generate(prompts.generate_statements(actual_output), Statements, cost=cost)
        return result.statements

    async def _generate_verdicts(self, input: str, statements: list[str], cost: Cost) -> RawVerdicts:
        if len(statements) == 0:
            return RawVerdicts(verdicts=[])
        return await self.llm.generate(prompts.generate_verdicts(input, statements), RawVerdicts, cost=cost)

    async def _generate_reason(
        self, input: str, raw_verdicts: RawVerdicts, verdicts: list[str | None], score: float, cost: Cost
    ) -> str:
        irrelevant_statements = [raw.reason for raw, v in zip(raw_verdicts.verdicts, verdicts) if v == NO]
        prompt = prompts.generate_reason(irrelevant_statements, input, format(score, ".2f"))
        result = await self.llm.generate(prompt, ScoreReason, cost=cost)
        return result.reason

    @staticmethod
    def _summary(verdicts: list[str | None]) -> str:
        counts = {v: sum(1 for x in verdicts if x == v) for v in (YES, BORDERLINE, NO)}
        judged = sum(counts.values())
        return f"판정된 진술 {judged}개 중 yes {counts[YES]}개, borderline {counts[BORDERLINE]}개, no {counts[NO]}개입니다."
