# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/answer_relevancy/metric.py (class AnswerRelevancy;
# the metric's public name is ResponseRelevancy)
# Changes:
#   - Korean prompts; inputs and outputs use the Chaejeom schema.
#   - Each generated question's noncommittal flag and cosine similarity are
#     recorded as units.
#   - Upstream's NaN score is reported as score=None.
#   - Adds a Korean `reason`; it does not affect the score.
#   - The LLM client re-asks with the validation error when a response does not
#     match the JSON schema (a retry Chaejeom adds; upstream has none).

import math

import numpy as np

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.ragas.prompts.response_relevancy import (
    AnswerRelevanceInput,
    AnswerRelevanceOutput,
    AnswerRelevancePrompt,
)
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="ragas",
    version="v0.4.3",
    commit="4ecab384fda829ca50bec3f07cc49589d756e172",
    method="답변만 보고 역질문을 strictness 번 생성해 원래 질문과의 코사인 유사도를 평균하고, 모두 회피성이면 0",
)

RAW_SCALE = "-1~1 (역질문과 원래 질문의 평균 코사인 유사도)"


class ResponseRelevancyOptions(MetricOptions):
    strictness: int = 3


@register
class ResponseRelevancy(Metric):
    """RAGAS response relevancy: similarity between the query and questions generated from the answer."""

    metric_id = "ragas.response_relevancy"
    axis = "answer_relevance"
    source = SOURCE
    requires = frozenset({"query", "answer", "embeddings"})
    Options = ResponseRelevancyOptions

    prompt = AnswerRelevancePrompt()

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        if not sample.query:
            raise ValueError("query 가 비어 있습니다.")
        if not sample.answer:
            raise ValueError("answer 가 비어 있습니다.")

        cost = Cost()
        generated_questions = []
        noncommittal_flags = []

        for i in range(self.options.strictness):
            input_data = AnswerRelevanceInput(response=sample.answer)
            prompt_string = self.prompt.to_string(input_data)
            # The same prompt is sent `strictness` times on purpose; `variant` keeps
            # the cache from returning the first response for every call.
            result = await self.llm.generate(prompt_string, AnswerRelevanceOutput, cost=cost, variant=i)

            if result.question:
                generated_questions.append(result.question)
                noncommittal_flags.append(result.noncommittal)

        if not generated_questions:
            return self.result(
                score=0.0,
                raw_scale=RAW_SCALE,
                reason="역질문을 만들지 못해 0점입니다.",
                cost=cost,
            )

        all_noncommittal = np.all(noncommittal_flags)

        question_vec = np.asarray((await self.embeddings.embed([sample.query]))[0]).reshape(1, -1)
        gen_question_vec = np.asarray(await self.embeddings.embed(generated_questions)).reshape(
            len(generated_questions), -1
        )

        norm = np.linalg.norm(gen_question_vec, axis=1) * np.linalg.norm(question_vec, axis=1)
        cosine_sim = (
            np.dot(gen_question_vec, question_vec.T).reshape(
                -1,
            )
            / norm
        )

        score = float(cosine_sim.mean() * int(not all_noncommittal))
        mean_similarity = float(cosine_sim.mean())

        units = [
            Unit(type="generated_question", text=q, verdict=flag, score=float(sim))
            for q, flag, sim in zip(generated_questions, noncommittal_flags, cosine_sim)
        ]
        if math.isnan(score):
            return self.result(
                units=units,
                raw_scale=RAW_SCALE,
                reason="코사인 유사도를 계산할 수 없어 점수를 낼 수 없습니다.",
                cost=cost,
            )
        if all_noncommittal:
            reason = f"역질문 {len(generated_questions)}개 모두 회피성 답변으로 판정되어 0점입니다."
        else:
            reason = f"역질문 {len(generated_questions)}개와 원래 질문의 평균 코사인 유사도는 {mean_similarity:.2f}입니다."
        return self.result(
            score=score,
            raw_score=mean_similarity,
            raw_scale=RAW_SCALE,
            units=units,
            reason=reason,
            cost=cost,
        )
