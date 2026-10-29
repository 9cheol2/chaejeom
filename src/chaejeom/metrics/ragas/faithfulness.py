# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/faithfulness/metric.py
# Changes:
#   - Korean prompts; inputs and outputs use the Chaejeom schema.
#   - Per-statement verdicts are recorded as units.
#   - Upstream's NaN score is reported as score=None.
#   - Adds a Korean `reason`; it does not affect the score.
#   - The LLM client re-asks with the validation error when a response does not
#     match the JSON schema (a retry Chaejeom adds; upstream has none).

from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.ragas.prompts.faithfulness import (
    NLIStatementInput,
    NLIStatementOutput,
    NLIStatementPrompt,
    StatementGeneratorInput,
    StatementGeneratorOutput,
    StatementGeneratorPrompt,
)
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit

SOURCE = Source(
    framework="ragas",
    version="v0.4.3",
    commit="4ecab384fda829ca50bec3f07cc49589d756e172",
    method="답변을 진술로 분해하고, 진술마다 문맥에서 직접 추론할 수 있는지 0/1 로 판정한 뒤 1의 비율을 계산",
)


@register
class Faithfulness(Metric):
    """RAGAS faithfulness: share of answer statements directly inferable from the contexts."""

    metric_id = "ragas.faithfulness"
    axis = "groundedness"
    source = SOURCE
    requires = frozenset({"query", "answer", "contexts"})

    statement_generator_prompt = StatementGeneratorPrompt()
    nli_statement_prompt = NLIStatementPrompt()

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        if not sample.answer:
            raise ValueError("answer 가 비어 있습니다.")
        if not sample.query:
            raise ValueError("query 가 비어 있습니다.")
        if not sample.contexts:
            raise ValueError("contexts 가 비어 있습니다.")

        cost = Cost()
        statements = await self._create_statements(sample.query, sample.answer, cost)
        if not statements:
            return self._result(None, [], cost, "답변에서 진술을 만들지 못해 점수를 계산할 수 없습니다.")

        context_str = "\n".join(c.text for c in sample.contexts)
        verdicts = await self._create_verdicts(statements, context_str, cost)
        score = self._compute_score(verdicts)

        units = [
            Unit(type="statement", text=v.statement, verdict=v.verdict, reason=v.reason)
            for v in verdicts.statements
        ]
        if score is None:
            return self._result(None, units, cost, "판정 결과가 비어 있어 점수를 계산할 수 없습니다.")
        supported = sum(1 for v in verdicts.statements if v.verdict)
        reason = f"진술 {len(verdicts.statements)}개 중 {supported}개가 문맥에서 직접 추론됩니다."
        return self._result(score, units, cost, reason)

    async def _create_statements(self, question: str, answer: str, cost: Cost) -> list[str]:
        input_data = StatementGeneratorInput(question=question, answer=answer)
        prompt_str = self.statement_generator_prompt.to_string(input_data)
        result = await self.llm.generate(prompt_str, StatementGeneratorOutput, cost=cost)
        return result.statements

    async def _create_verdicts(self, statements: list[str], context: str, cost: Cost) -> NLIStatementOutput:
        input_data = NLIStatementInput(context=context, statements=statements)
        prompt_str = self.nli_statement_prompt.to_string(input_data)
        return await self.llm.generate(prompt_str, NLIStatementOutput, cost=cost)

    @staticmethod
    def _compute_score(verdicts: NLIStatementOutput) -> float | None:
        if not verdicts.statements:
            return None
        faithful_statements = sum(1 if statement.verdict else 0 for statement in verdicts.statements)
        return faithful_statements / len(verdicts.statements)

    def _result(self, score: float | None, units: list[Unit], cost: Cost, reason: str) -> MetricResult:
        return self.result(
            score=score,
            raw_score=score,
            raw_scale="0~1 (직접 추론되는 진술의 비율)",
            units=units,
            reason=reason,
            cost=cost,
        )
