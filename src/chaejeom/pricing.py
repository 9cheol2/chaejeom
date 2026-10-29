"""Model prices and cost estimates.

Costs multiply API-reported token counts by the prices below. Prices change, so the UI always
labels them as estimates. Cached responses cost nothing. Embedding costs ($0.02-0.13 per 1M
tokens, well under $0.001 per evaluation) are ignored.
"""

from statistics import fmean
from typing import NamedTuple

# USD per 1M tokens (input, output), from OpenAI's official price list as of 2026-10.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-6-luna": (0.10, 0.50),
}
PRICES_AS_OF = "2026-10"


def usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Return the cost in USD, or ``None`` if the model has no known price."""
    price = PRICES.get(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


# Average (input, output) tokens per metric per sample, measured uncached with gpt-4o-mini on the
# 6 samples in examples/samples.jsonl. Estimates scale these to the user's sample sizes.
TOKENS_PER_EVAL: dict[str, tuple[int, int]] = {
    "ragas.faithfulness": (1319, 203),
    "ragas.context_relevance": (1206, 12),
    "ragas.response_relevancy": (1593, 91),
    "deepeval.faithfulness": (1416, 166),
    "deepeval.contextual_relevancy": (1128, 200),
    "deepeval.answer_relevancy": (1101, 138),
    "trulens.groundedness": (759, 95),
    "trulens.context_relevance": (1126, 336),
    "trulens.answer_relevance": (554, 109),
    "chaejeom.groundedness": (1427, 129),
    "chaejeom.context_relevance": (724, 88),
    "chaejeom.answer_relevance": (798, 86),
}
# Averages of the measured samples: characters, context chunks, answer sentences.
REFERENCE = (133.0, 5 / 3, 4 / 3)

# Metrics whose cost grows with the number of chunks or answer sentences.
# "calls": one call per unit, so input and output both grow; "output": a single call whose output grows.
GROWTH: dict[str, tuple[str, str]] = {
    "trulens.context_relevance": ("chunks", "calls"),
    "deepeval.contextual_relevancy": ("chunks", "calls"),
    "trulens.groundedness": ("sentences", "calls"),
    "chaejeom.context_relevance": ("chunks", "output"),
    "chaejeom.groundedness": ("sentences", "output"),
    "ragas.faithfulness": ("sentences", "output"),
    "deepeval.faithfulness": ("sentences", "output"),
}


class SampleStats(NamedTuple):
    """Average characters, context chunks, and answer sentences per sample."""

    chars: float
    chunks: float
    sentences: float


def sample_chars(query: str, contexts: list[str], answer: str) -> int:
    return len(query) + sum(len(c) for c in contexts) + len(answer)


def sample_stats(samples) -> SampleStats:
    from chaejeom.text import split_sentences

    return SampleStats(
        fmean(sample_chars(s.query, [c.text for c in s.contexts], s.answer) for s in samples),
        fmean(len(s.contexts) for s in samples),
        fmean(len(split_sentences(s.answer) or [s.answer]) if s.answer else 0 for s in samples),
    )


def estimate_usd(metric_ids: list[str], stats: SampleStats, n_samples: int, repeats: int, model: str) -> float | None:
    """Roughly estimate the uncached cost of an evaluation.

    Input tokens are modeled as half fixed (prompt template) and half proportional to sample
    length; metrics listed in ``GROWTH`` also scale with chunk or sentence counts.

    Returns:
        Estimated USD, or ``None`` if the model price or any metric's token profile is unknown.
    """
    price = PRICES.get(model)
    if price is None or any(m not in TOKENS_PER_EVAL for m in metric_ids):
        return None
    length = 0.5 + 0.5 * stats.chars / REFERENCE[0]
    units = {"chunks": max(stats.chunks, 1) / REFERENCE[1], "sentences": max(stats.sentences, 1) / REFERENCE[2]}
    total = 0.0
    for metric_id in metric_ids:
        input_tokens, output_tokens = TOKENS_PER_EVAL[metric_id]
        unit, kind = GROWTH.get(metric_id, ("", ""))
        ratio = units.get(unit, 1.0)
        calls = ratio if kind == "calls" else 1.0
        output = ratio if kind else 1.0
        total += input_tokens * length * calls * price[0] + output_tokens * output * price[1]
    return total / 1_000_000 * n_samples * repeats
