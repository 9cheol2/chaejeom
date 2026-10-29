"""Judge prompts of the ported upstream metrics, as shown by `/prompt`.

Each step renders the exact prompt the metric sends, with inputs left as
placeholders such as `{query}`. Ported metrics are kept as-is, so these are
display-only.
"""

from chaejeom.metrics.deepeval.prompts import answer_relevancy as de_answer
from chaejeom.metrics.deepeval.prompts import contextual_relevancy as de_context
from chaejeom.metrics.deepeval.prompts import faithfulness as de_faith
from chaejeom.metrics.ragas.prompts.context_relevance import (
    ContextRelevanceInput,
    ContextRelevanceJudge1Prompt,
    ContextRelevanceJudge2Prompt,
)
from chaejeom.metrics.ragas.prompts.faithfulness import (
    NLIStatementInput,
    NLIStatementPrompt,
    StatementGeneratorInput,
    StatementGeneratorPrompt,
)
from chaejeom.metrics.ragas.prompts.response_relevancy import AnswerRelevanceInput, AnswerRelevancePrompt
from chaejeom.metrics.trulens import prompts as rag

# (step name, prompt). Metrics that send separate system and user messages
# list each message as its own step.
Step = tuple[str, str]


def upstream_prompts(metric_id: str) -> list[Step]:
    """Return the judge prompt of each step of an upstream metric."""
    steps: dict[str, list[Step]] = {
        "ragas.faithfulness": [
            ("Statement generation", StatementGeneratorPrompt().to_string(StatementGeneratorInput(question="{query}", answer="{answer}"))),
            ("Verdict", NLIStatementPrompt().to_string(NLIStatementInput(context="{contexts}", statements=["{statement}"]))),
        ],
        "ragas.context_relevance": [
            ("Judge 1", ContextRelevanceJudge1Prompt().to_string(ContextRelevanceInput(user_input="{query}", context="{contexts}"))),
            ("Judge 2", ContextRelevanceJudge2Prompt().to_string(ContextRelevanceInput(user_input="{query}", context="{contexts}"))),
        ],
        "ragas.response_relevancy": [
            ("Question generation", AnswerRelevancePrompt().to_string(AnswerRelevanceInput(response="{answer}"))),
        ],
        "deepeval.faithfulness": [
            ("Truths", de_faith.generate_truths("{contexts}", None)),
            ("Claims", de_faith.generate_claims("{answer}")),
            ("Verdicts", de_faith.generate_verdicts(["{claim}"], "{truths}")),
            ("Reason", de_faith.generate_reason(["{contradiction}"], "{score}")),
        ],
        "deepeval.answer_relevancy": [
            ("Statements", de_answer.generate_statements("{answer}")),
            ("Verdicts", de_answer.generate_verdicts("{query}", ["{statement}"])),
            ("Reason", de_answer.generate_reason(["{irrelevant_statement}"], "{query}", "{score}")),
        ],
        "deepeval.contextual_relevancy": [
            ("Verdicts", de_context.generate_verdicts("{query}", "{context}")),
            ("Reason", de_context.generate_reason("{query}", ["{irrelevant_statement}"], ["{relevant_statement}"], "{score}")),
        ],
        "trulens.groundedness": [
            ("Sentence split (system)", rag.Groundedness.sentences_splitter_prompt),
            ("Verdict (system)", rag.Groundedness.system_prompt),
            ("Verdict (user)", rag.Groundedness.user_prompt),
            ("Trivial statements (system)", rag.Trivial.system_prompt),
            ("Trivial statements (user)", rag.Trivial.user_prompt),
        ],
        "trulens.context_relevance": [
            ("Verdict (system)", rag.ContextRelevance.default_cot_prompt),
            ("Verdict (user)", rag.ContextRelevance.user_prompt),
        ],
        "trulens.answer_relevance": [
            ("Verdict (system)", rag.PromptResponseRelevance.system_prompt),
            ("Verdict (user)", rag.PromptResponseRelevance.user_prompt),
        ],
    }
    return steps[metric_id]
