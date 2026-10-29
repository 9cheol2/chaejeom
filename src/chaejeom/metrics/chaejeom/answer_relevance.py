from chaejeom import __version__
from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.chaejeom import prompts
from chaejeom.metrics.chaejeom.judging import DomainOptions, template_for
from chaejeom.metrics.chaejeom.schema import AnswerRelevanceOutput
from chaejeom.metrics.chaejeom.scoring import RAW_SCALE, SAYS_MISSING, answer_kind, answer_relevance_level, find_quote
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="chaejeom",
    version=__version__,
    commit="",
    method="회피 여부, 같은 대상인지, 묻는 것을 다루는지, 직접 답하는지 예/아니오로 답하게 해 응한 방식(직접, 간접, 다른 측면, 다른 주제, 회피)을 정하고, 관계없는 부분과 함께 단계 규칙으로 0~1 다섯 단계 점수를 정함",
)

KIND_LABELS = {
    "direct": "질문에 직접 답함",
    "indirect": "일반적인 설명이나 조건만 말함",
    "other_aspect": "같은 주제의 다른 것을 답함",
    "off_topic": "다른 주제를 답함",
    "evasive": "답을 피함",
    "declined": "자료에 없다고 밝힘",
}


@register
class AnswerRelevance(Metric):
    """Whether the answer addresses what the question asks.

    Irrelevant parts the judge lists are kept only if they appear verbatim in the
    answer, so a fabricated quote cannot cost points.
    """

    metric_id = "chaejeom.answer_relevance"
    axis = "answer_relevance"
    source = SOURCE
    Options = DomainOptions
    requires = frozenset({"query", "answer"})

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        prompt = prompts.answer_relevance(sample.query, sample.answer, template_for(self.options, self.metric_id))
        output = await self.llm.generate(prompt, AnswerRelevanceOutput, cost=cost)

        parts = [p.strip() for p in output.irrelevant_parts if find_quote(p, {"answer": sample.answer})]
        # "Not in the materials" leaves the answer unscored, so it must be backed by a sentence the answer really has
        # and that says something is missing; otherwise a judge mislabel would hide an off-target answer from the score
        # (the judge has quoted an unrelated answer sentence as the "declining" one).
        quote = output.declines_quote
        declines = output.declines_missing and find_quote(quote, {"answer": sample.answer}) is not None and bool(SAYS_MISSING.search(quote))
        kind = answer_kind(output.evasive, output.same_target, output.discusses_asked, output.answers_directly, declines)
        score, rule = answer_relevance_level(kind, bool(parts))
        targets = f" (질문의 대상: {output.question_target}, 답변의 대상: {output.answer_target})" if output.question_target else ""
        units = [
            Unit(type="judge", text=KIND_LABELS[kind] + targets, verdict=kind, reason=output.reason or None),
            *(Unit(type="statement", text=p, verdict="irrelevant") for p in parts),
        ]
        return self.result(score=score, raw_scale=RAW_SCALE, units=units, reason=rule, cost=cost)
