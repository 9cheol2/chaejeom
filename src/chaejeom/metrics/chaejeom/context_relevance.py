from chaejeom import __version__
from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.chaejeom import prompts
from chaejeom.metrics.chaejeom.judging import DomainOptions, judge_all, template_for
from chaejeom.metrics.chaejeom.schema import ContextRelevanceOutput
from chaejeom.metrics.chaejeom.scoring import (
    IRRELEVANT,
    PARTIAL,
    RAW_SCALE,
    RELEVANT,
    chunk_verdict,
    context_relevance_level,
)
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="chaejeom",
    version=__version__,
    commit="",
    method="문맥 조각마다 질문의 대상을 다루는지, 묻는 것을 담는지 예/아니오로 답하게 해 관련성(관련, 일부 관련, 관련 없음)을 정하고, 단계 규칙으로 0~1 다섯 단계 점수를 정함",
)


@register
class ContextRelevance(Metric):
    """Whether the retrieved chunks are relevant to the question."""

    metric_id = "chaejeom.context_relevance"
    axis = "context_relevance"
    source = SOURCE
    Options = DomainOptions
    requires = frozenset({"query", "contexts"})

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        template = template_for(self.options, self.metric_id)
        prompt = prompts.context_relevance(sample.query, [c.text for c in sample.contexts], template)
        expected = [f"c{i}" for i in range(1, len(sample.contexts) + 1)]
        _, judged, missing = await judge_all(self.llm, prompt, ContextRelevanceOutput, expected, lambda o: o.chunks, cost)
        if missing:
            return self.result(raw_scale=RAW_SCALE, cost=cost, error=f"판정에서 빠진 문맥 조각이 있습니다: {', '.join(missing)}")

        units = [
            Unit(
                type="chunk",
                text=context.text,
                verdict=chunk_verdict(judged[f"c{i}"].about_target, judged[f"c{i}"].has_answer),
                reason=judged[f"c{i}"].reason.strip() or None,
                context_ids=[context.id],
            )
            for i, context in enumerate(sample.contexts, start=1)
        ]
        verdicts = [u.verdict for u in units]
        score, rule = context_relevance_level(verdicts)
        rule += f" (관련 {verdicts.count(RELEVANT)}, 일부 관련 {verdicts.count(PARTIAL)}, 관련 없음 {verdicts.count(IRRELEVANT)})"
        return self.result(score=score, raw_scale=RAW_SCALE, units=units, reason=rule, cost=cost)
