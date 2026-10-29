# Adapted from trulens 2.16.0 (MIT), commit 1f65a310cd5bdaef3ea7be76e98022f574cea39c
#   src/feedback/trulens/feedback/llm_provider.py (relevance_with_cot_reasons)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema.
# - An unparsable score is reported as score=None with an error instead of upstream's -1.0.
# - The judge's supporting evidence is used as the reason.
# - Judge responses without a parsable score are not cached.

from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.trulens.prompts import PromptResponseRelevance as Prompts
from chaejeom.metrics.trulens.scoring import has_score, parse_score_and_reasons
from chaejeom.schema import Cost, EvalSample, MetricResult, Source

SOURCE = Source(
    framework="trulens",
    version="2.16.0",
    commit="1f65a310cd5bdaef3ea7be76e98022f574cea39c",
    method="프롬프트와 응답 전체를 놓고 관련성을 0~3 으로 한 번 채점(CoT)",
)


@register
class AnswerRelevance(Metric):
    """TruLens answer relevance: one 0-3 chain-of-thought rating of the whole response."""

    metric_id = "trulens.answer_relevance"
    axis = "answer_relevance"
    source = SOURCE
    requires = frozenset({"query", "answer"})

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        user_prompt = Prompts.user_prompt.format(prompt=sample.query, response=sample.answer)
        response = await self.llm.complete(user_prompt, system=Prompts.system_prompt, cost=cost, accept=has_score)
        judgment = parse_score_and_reasons(response)

        if judgment.score is None:
            return self.result(raw_scale="0~3", cost=cost, error="채점 응답에서 점수를 읽지 못했습니다.")
        return self.result(
            score=judgment.normalized,
            raw_score=judgment.score,
            raw_scale="0~3",
            reason=judgment.supporting_evidence or None,
            cost=cost,
        )
