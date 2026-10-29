from chaejeom import __version__
from chaejeom.metrics.base import Metric, register
from chaejeom.metrics.chaejeom import prompts
from chaejeom.metrics.chaejeom.judging import DomainOptions, judge_all, label, template_for
from chaejeom.metrics.chaejeom.schema import GroundednessOutput
from chaejeom.metrics.chaejeom.scoring import (
    CONTRADICTED,
    RAW_SCALE,
    SAYS_MISSING,
    SUPPORTED,
    UNSUPPORTED,
    find_quote,
    groundedness_level,
    missing_numbers,
)
from chaejeom.schema import Cost, EvalSample, MetricResult, Source, Unit
from chaejeom.text import split_sentences

SOURCE = Source(
    framework="chaejeom",
    version=__version__,
    commit="",
    method="답변의 문장마다 사실 진술을 뽑아 핵심 여부와 문맥 근거(뒷받침, 문맥에 없음, 어긋남)를 표시하고, 단계 규칙으로 0~1 다섯 단계 점수를 정함",
)


def _lines(quote: str) -> list[str]:
    return [line.strip() for line in quote.splitlines() if line.strip()]


def find_quotes(quote: str, texts: dict[str, str], cited: str) -> list[str]:
    """Locate each line of a (possibly multi-chunk) quote in the contexts.

    A quote spanning several chunks arrives as newline-joined lines. Each line is
    searched in the chunks the judge cited first, then in all chunks.

    Args:
        quote: Quote copied by the judge, one line per source sentence.
        texts: Context text keyed by prompt label (``"c1"``, ``"c2"``, ...).
        cited: Labels the judge cited, e.g. ``"c1"`` or ``"c1, c2"``.

    Returns:
        Matching labels in order of first appearance, without duplicates, or an
        empty list if any line cannot be found.
    """
    preferred = [label(c) for c in cited.split(",") if c.strip()]
    found: list[str] = []
    for line in _lines(quote):
        cited_match = next((p for p in preferred if p in texts and find_quote(line, {p: texts[p]})), None)
        match = cited_match or find_quote(line, texts)
        if match is None:
            return []
        if match not in found:
            found.append(match)
    return found


SHORT_SENTENCE_CHARS = 6


def join_short(sentences: list[str]) -> list[str]:
    """Attach very short sentences without digits to the next sentence (or the previous one if last).

    The judge tends to skip sentences like "네." entirely, which fails the
    every-sentence-judged check even on retry. They carry no facts, so joining
    them does not change the verdicts.
    """
    joined: list[str] = []
    carry = ""
    for sentence in sentences:
        short = len("".join(sentence.split())) <= SHORT_SENTENCE_CHARS and not any(ch.isdigit() for ch in sentence)
        if short:
            carry = f"{carry} {sentence}".strip()
            continue
        joined.append(f"{carry} {sentence}".strip())
        carry = ""
    if carry:
        if joined:
            joined[-1] = f"{joined[-1]} {carry}"
        else:
            joined.append(carry)
    return joined


def merge_repeated(statements: list) -> list:
    """Merge copies of one statement that the judge repeated once per supporting chunk.

    When evidence for a statement is split across chunks, the judge sometimes
    repeats the statement per chunk, each copy quoting only part of the evidence.
    Merging joins the quotes with newlines and the context labels with commas so
    the statement is checked against all of its evidence. Only copies with the
    same verdict are merged.
    """
    merged: dict[tuple[str, str], object] = {}
    for item in statements:
        key = ("".join(item.statement.split()), item.verdict)
        if key not in merged:
            merged[key] = item.model_copy()
            continue
        first = merged[key]
        if item.quote.strip():
            first.quote = "\n".join(q for q in (first.quote.strip(), item.quote.strip()) if q)
        if item.context_id.strip():
            first.context_id = ", ".join(c for c in (first.context_id.strip(), item.context_id.strip()) if c)
        first.core = first.core or item.core
    return list(merged.values())


@register
class Groundedness(Metric):
    """Whether each factual statement in the answer is supported by the contexts.

    The answer is split into numbered sentences (kiwipiepy) and the judge must
    cover every one, so no statement is silently skipped. Every quote the judge
    cites is verified against the contexts; a supported or contradicted verdict
    whose quote cannot be found becomes unsupported, which keeps the judge from
    vouching for statements from its own knowledge.
    """

    metric_id = "chaejeom.groundedness"
    axis = "groundedness"
    source = SOURCE
    Options = DomainOptions
    requires = frozenset({"query", "answer", "contexts"})

    async def ameasure(self, sample: EvalSample) -> MetricResult:
        cost = Cost()
        sentences = join_short(split_sentences(sample.answer)) or [sample.answer]
        template = template_for(self.options, self.metric_id)
        prompt = prompts.groundedness(sample.query, [c.text for c in sample.contexts], sentences, template)
        expected = [f"s{i}" for i in range(1, len(sentences) + 1)]
        _, judged_sentences, missing = await judge_all(self.llm, prompt, GroundednessOutput, expected, lambda o: o.sentences, cost)
        if missing:
            return self.result(raw_scale=RAW_SCALE, cost=cost, error=f"판정에서 빠진 답변 문장이 있습니다: {', '.join(missing)}")

        ids = {f"c{i}": c.id for i, c in enumerate(sample.contexts, start=1)}
        texts = {f"c{i}": c.text for i, c in enumerate(sample.contexts, start=1)}
        units: list[Unit] = []
        for sentence_id in expected:
            for judged in merge_repeated(judged_sentences[sentence_id].statements):
                verdict, found, reason = judged.verdict, [], judged.reason.strip()
                if judged.absence and verdict == SUPPORTED and SAYS_MISSING.search(judged.statement):
                    # A correct absence claim has nothing to quote; this is the only verdict accepted without a quote,
                    # so it also requires the statement to actually say something is missing ("없", "않", "못").
                    # Otherwise a mislabelled hedge like "수수료는 상황에 따라 다를 수 있다" would pass for free.
                    # The judge is told to search for the asked value first and mark the claim contradicted if it finds it.
                    # Do not override a supported verdict just because a quote is present: on real data the judge often
                    # quotes a nearby figure (another period) while correctly finding the asked value absent.
                    reason = f"{reason} (질문이 묻는 정보가 문맥에 없다는 진술입니다.)".strip()
                elif verdict in (SUPPORTED, CONTRADICTED):
                    found = find_quotes(judged.quote, texts, judged.context_id)
                    if not found:
                        verdict = UNSUPPORTED
                        reason = f"{reason} (근거로 든 문장을 문맥에서 찾지 못해 '문맥에 없음'으로 처리했습니다.)".strip()
                    else:
                        reason = f'{reason} 근거: "{" / ".join(_lines(judged.quote))}"'.strip()
                        # Numbers missing from the quote are flagged for review, not penalised: periods often appear
                        # only in the chunk header, and comparison answers often use computed values.
                        numbers = missing_numbers(judged.statement, "\n".join(texts[c] for c in found)) if verdict == SUPPORTED else []
                        if numbers:
                            reason = f"{reason} (확인 필요: 진술의 수치 {', '.join(numbers)} 이(가) 인용한 조각에 없습니다. 계산한 값인지 확인하세요.)"
                units.append(
                    Unit(
                        type="statement",
                        text=judged.statement,
                        verdict=verdict,
                        reason=reason or None,
                        context_ids=[ids[c] for c in found],
                        core=judged.core,
                    )
                )

        score, rule = groundedness_level([(u.verdict, bool(u.core)) for u in units])
        counts = {v: sum(1 for u in units if u.verdict == v) for v in (SUPPORTED, UNSUPPORTED, CONTRADICTED)}
        if units:
            rule += (
                f" (진술 {len(units)}개: 뒷받침 {counts[SUPPORTED]}, 문맥에 없음 {counts[UNSUPPORTED]},"
                f" 어긋남 {counts[CONTRADICTED]})"
            )
        return self.result(score=score, raw_scale=RAW_SCALE, units=units, reason=rule, cost=cost)
