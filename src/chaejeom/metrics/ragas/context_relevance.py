# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/context_relevance/metric.py
# Changes:
#   - Korean prompts; inputs and outputs use the Chaejeom schema.
#   - Each judge prompt's rating is recorded as a unit.
#   - Upstream's NaN score is reported as score=None.
#   - Adds a Korean `reason`; it does not affect the score.
#   - The LLM client's JSON-format retry is disabled so only upstream's
#     max_retries loop retries (same number of calls as upstream).
#   - When both judge prompts fail with exceptions, the score is None as
#     upstream, but the last exception message is kept in `error`.

import math

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.ragas.prompts.base import RagasPrompt
from chaejeom.metrics.ragas.prompts.context_relevance import (
    ContextRelevanceInput,
    ContextRelevanceJudge1Prompt,
    ContextRelevanceJudge2Prompt,
    ContextRelevanceOutput,
)
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="ragas",
    version="v0.4.3",
    commit="4ecab384fda829ca50bec3f07cc49589d756e172",
    method="문맥 전체를 이어 붙여 두 판정 프롬프트가 각각 0/1/2 로 관련성을 매기고, 2로 나눈 두 점수를 평균",
)

RAW_SCALE = "0~2 (판정 프롬프트 2개의 관련성 점수 평균)"


class ContextRelevanceOptions(MetricOptions):
    max_retries: int = 5


@register
class ContextRelevance(Metric):
    """RAGAS context relevance: mean of two judge prompts' 0/1/2 ratings, scaled to 0-1."""

    metric_id = "ragas.context_relevance"
    axis = "context_relevance"
    source = SOURCE
    requires = frozenset({"query", "contexts"})
    Options = ContextRelevanceOptions

    judge1_prompt = ContextRelevanceJudge1Prompt()
    judge2_prompt = ContextRelevanceJudge2Prompt()

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        if not sample.query:
            raise ValueError("query 가 비어 있습니다.")
        if not sample.contexts:
            raise ValueError("contexts 가 비어 있습니다.")

        user_input = sample.query
        context_str = "\n".join(c.text for c in sample.contexts)
        if not user_input.strip() or not context_str.strip():
            return self._edge_case("질문이나 문맥이 비어 있어 0점입니다.")
        if user_input.strip() == context_str.strip():
            return self._edge_case("문맥이 질문과 같아 0점입니다.")
        if context_str.strip() in user_input.strip():
            return self._edge_case("문맥이 질문 안에 포함되어 있어 0점입니다.")

        cost = Cost()
        judge1_rating, judge1_error = await self._get_judge_rating(self.judge1_prompt, user_input, context_str, cost)
        judge2_rating, judge2_error = await self._get_judge_rating(self.judge2_prompt, user_input, context_str, cost)

        score = self._average_scores(judge1_rating / 2.0, judge2_rating / 2.0)

        ratings = [judge1_rating, judge2_rating]
        units = [
            Unit(type="judge", text=f"판정 프롬프트 {i}", verdict=None if math.isnan(r) else int(r))
            for i, r in enumerate(ratings, start=1)
        ]
        if math.isnan(score):
            error = None
            if judge1_error is not None and judge2_error is not None:
                error = f"두 판정 프롬프트 모두 오류로 실패했습니다: {str(judge2_error) or type(judge2_error).__name__}"
            return self.result(
                units=units,
                raw_scale=RAW_SCALE,
                reason="두 판정 프롬프트 모두 유효한 관련성 점수를 받지 못해 점수를 계산할 수 없습니다.",
                cost=cost,
                error=error,
            )
        parts = [f"판정 프롬프트 {i} {'실패' if math.isnan(r) else f'{int(r)}점'}" for i, r in enumerate(ratings, start=1)]
        return self.result(
            score=score,
            raw_score=score * 2.0,
            raw_scale=RAW_SCALE,
            units=units,
            reason=f"관련성 점수(0~2): {', '.join(parts)}.",
            cost=cost,
        )

    async def _get_judge_rating(
        self, prompt_obj: RagasPrompt, user_input: str, context: str, cost: Cost
    ) -> tuple[float, Exception | None]:
        """Return the rating (NaN on failure) and the exception if the last attempt raised."""
        max_retries = self.options.max_retries
        for retry in range(max_retries):
            try:
                input_data = ContextRelevanceInput(user_input=user_input, context=context)
                prompt_str = prompt_obj.to_string(input_data)
                # Upstream retries only through this loop, so the client's format
                # retry is off. `variant` keeps the cache from replaying the previous
                # attempt's invalid response.
                result = await self.llm.generate(
                    prompt_str, ContextRelevanceOutput, cost=cost, max_attempts=1, variant=retry
                )
                rating = result.rating

                if rating in [0, 1, 2]:
                    return float(rating), None
                else:
                    if retry < max_retries - 1:
                        continue
                    else:
                        return float("nan"), None
            except Exception as e:
                if retry < max_retries - 1:
                    continue
                else:
                    return float("nan"), e
        return float("nan"), None

    @staticmethod
    def _average_scores(score1: float, score2: float) -> float:
        if not math.isnan(score1) and not math.isnan(score2):
            return (score1 + score2) / 2.0
        elif not math.isnan(score1):
            return score1
        elif not math.isnan(score2):
            return score2
        else:
            return float("nan")

    def _edge_case(self, reason: str) -> MetricResult:
        return self.result(score=0.0, raw_score=0.0, raw_scale=RAW_SCALE, reason=reason)
