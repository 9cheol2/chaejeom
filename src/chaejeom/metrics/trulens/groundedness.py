# Adapted from trulens 2.16.0 (MIT), commit 1f65a310cd5bdaef3ea7be76e98022f574cea39c
#   src/feedback/trulens/feedback/llm_provider.py (groundedness_measure_with_cot_reasons, _remove_trivial_statements)
#
# Changes from upstream:
# - Korean prompts; inputs and outputs use the Chaejeom schema; per-sentence judgments
#   are recorded as units.
# - The default sentence splitter is kiwipiepy `split_into_sents` instead of nltk
#   `sent_tokenize`, whose punkt model targets English.
# - Contexts are joined with "\n\n" rather than inserted as a Python list repr
#   (f"{source}"), matching how TruLens joins passages elsewhere (_join_context_passages).
# - The trivial-statement response is parsed with ast.literal_eval instead of eval(), and
#   a response wrapped entirely in a code fence is unwrapped first.
# - Per-sentence judgments run concurrently with asyncio.gather instead of a thread pool.
# - If no judgment yields a parsable score, report score=None with an error instead of
#   upstream's -1.0.
# - Adds a Korean reason describing the score.
# - Judge responses without a parsable score, and trivial-statement responses that do
#   not parse as a list, are not cached.

import ast
import asyncio
import re

from chaejeom.metrics.base import Metric, MetricOptions, register
from chaejeom.metrics.trulens.prompts import Groundedness as Prompts
from chaejeom.metrics.trulens.prompts import Trivial
from chaejeom.metrics.trulens.scoring import Judgment, has_score, mean_graded_score, parse_score_and_reasons
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit
from chaejeom.text import split_sentences

SOURCE = Source(
    framework="trulens",
    version="2.16.0",
    commit="1f65a310cd5bdaef3ea7be76e98022f574cea39c",
    method="답변을 문장으로 나누고 사소한 문장을 뺀 뒤, 문장마다 근거 자료가 뒷받침하는 정도를 0~3 으로 채점해 평균",
)

_NUMBER_MARKER = re.compile(r"^\s*\d+[\.)]?\s*$")
_FENCED = re.compile(r"^```(?:python)?\s*(.*?)\s*```$", re.DOTALL)


class GroundednessOptions(MetricOptions):
    use_sent_tokenize: bool = True  # False: ask the LLM to split sentences
    filter_trivial_statements: bool = True


@register
class Groundedness(Metric):
    """TruLens groundedness: the mean 0-3 rating of how well the sources support each answer sentence."""

    metric_id = "trulens.groundedness"
    axis = "groundedness"
    source = SOURCE
    requires = frozenset({"answer", "contexts"})
    Options = GroundednessOptions

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        statement = sample.answer
        source = "\n\n".join(c.text for c in sample.contexts)

        if self.options.use_sent_tokenize:
            hypotheses = split_sentences(statement)
        else:
            response = await self.llm.complete(statement, system=Prompts.sentences_splitter_prompt, cost=cost)
            hypotheses = response.split("\n")

        hypotheses = [h for h in hypotheses if not _NUMBER_MARKER.match(h)]

        if self.options.filter_trivial_statements:
            hypotheses = await self._remove_trivial_statements(hypotheses, cost)
            if not hypotheses:
                return self.result(
                    score=0.0,
                    raw_score=0.0,
                    raw_scale="0~3 (문장별 점수 평균)",
                    reason="사소한 문장을 빼고 나니 평가할 문장이 없습니다.",
                    cost=cost,
                )

        judgments = await asyncio.gather(*(self._judge(source, h, cost) for h in hypotheses))
        units = [
            Unit(type="sentence", text=h, score=j.score, reason=j.supporting_evidence)
            for h, j in zip(hypotheses, judgments)
        ]

        raw = mean_graded_score(list(judgments))
        if raw is None:
            return self.result(
                units=units,
                raw_scale="0~3 (문장별 점수 평균)",
                cost=cost,
                error="모든 문장의 채점 응답에서 점수를 읽지 못했습니다.",
            )
        return self.result(
            score=raw / 3,
            raw_score=raw,
            raw_scale="0~3 (문장별 점수 평균)",
            units=units,
            reason=f"문장 {len(units)}개의 근거성 점수 평균은 {raw:.2f}/3 입니다.",
            cost=cost,
        )

    async def _judge(self, source: str, hypothesis: str, cost: Cost) -> Judgment:
        user_prompt = Prompts.user_prompt.format(premise=source, hypothesis=hypothesis)
        response = await self.llm.complete(user_prompt, system=Prompts.system_prompt, cost=cost, accept=has_score)
        return parse_score_and_reasons(response)

    async def _remove_trivial_statements(self, statements: list[str], cost: Cost) -> list[str]:
        user_prompt = Trivial.user_prompt.format(statements=str(statements))
        response = await self.llm.complete(
            user_prompt,
            system=Trivial.system_prompt,
            cost=cost,
            accept=lambda r: _parse_statement_list(r) is not None,
        )
        result = _parse_statement_list(response)
        return statements if result is None else result


def _parse_statement_list(response: str) -> list[str] | None:
    """Parse a Python list literal from the response, or return None if it is not one."""
    text = response.strip()
    fenced = _FENCED.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        result = ast.literal_eval(text)
    except Exception:
        return None
    if isinstance(result, list):
        return [str(item) for item in result]
    return None
