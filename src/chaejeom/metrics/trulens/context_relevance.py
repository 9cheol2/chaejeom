# Adapted from trulens 2.16.0 (MIT), commit 1f65a310cd5bdaef3ea7be76e98022f574cea39c
#   src/feedback/trulens/feedback/llm_provider.py (context_relevance_with_cot_reasons)
#   src/core/trulens/core/batch.py (per-chunk aggregation: np.mean over parsable scores)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema; per-chunk judgments are
#   recorded as units.
# - Upstream runs a separate feedback call per chunk and averages at the app level; here
#   one metric makes the per-chunk calls and averages them.
# - If no chunk yields a parsable score, report score=None with an error instead of
#   upstream's -1.0.
# - Adds a Korean reason describing the score.
# - Judge responses without a parsable score are not cached.

import asyncio

from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.trulens.prompts import ContextRelevance as Prompts
from chaejeom.metrics.trulens.scoring import Judgment, has_score, mean_graded_score, parse_score_and_reasons
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="trulens",
    version="2.16.0",
    commit="1f65a310cd5bdaef3ea7be76e98022f574cea39c",
    method="문맥 조각마다 사용자 질의와의 관련성을 0~3 으로 채점(CoT)하고 평균",
)


@register
class ContextRelevance(Metric):
    """TruLens context relevance: the mean 0-3 relevance rating of each context chunk."""

    metric_id = "trulens.context_relevance"
    axis = "context_relevance"
    source = SOURCE
    requires = frozenset({"query", "contexts"})

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        judgments = await asyncio.gather(*(self._judge(sample.query, c.text, cost) for c in sample.contexts))
        units = [
            Unit(type="chunk", text=c.text, score=j.score, reason=j.supporting_evidence, context_ids=[c.id])
            for c, j in zip(sample.contexts, judgments)
        ]

        raw = mean_graded_score(list(judgments))
        if raw is None:
            return self.result(
                units=units,
                raw_scale="0~3 (문맥 조각별 점수 평균)",
                cost=cost,
                error="모든 문맥 조각의 채점 응답에서 점수를 읽지 못했습니다.",
            )
        return self.result(
            score=raw / 3,
            raw_score=raw,
            raw_scale="0~3 (문맥 조각별 점수 평균)",
            units=units,
            reason=f"문맥 조각 {len(units)}개의 관련성 점수 평균은 {raw:.2f}/3 입니다.",
            cost=cost,
        )

    async def _judge(self, question: str, context: str, cost: Cost) -> Judgment:
        user_prompt = Prompts.user_prompt.format(question=question, context=context)
        response = await self.llm.complete(
            user_prompt, system=Prompts.default_cot_prompt, cost=cost, accept=has_score
        )
        return parse_score_and_reasons(response)
