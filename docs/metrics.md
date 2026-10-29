# Metrics

**English | [한국어](metrics.ko.md)**

Chaejeom measures a RAG system on three axes. Every metric is reference-free: it needs only the query, the retrieved
contexts and the answer, never a ground-truth answer.

| Axis | Question it answers |
|---|---|
| Groundedness (context → answer) | Is what the answer says supported by the retrieved contexts? |
| Context relevance (query → context) | Did retrieval bring back what the question needs? |
| Answer relevance (query → answer) | Does the answer address the question? |

## Overview

| Axis | Metric id | Method | Scale |
|---|---|---|---|
| Groundedness | [`ragas.faithfulness`](https://github.com/vibrantlabsai/ragas/tree/4ecab384fda829ca50bec3f07cc49589d756e172/src/ragas/metrics/collections/faithfulness) | Splits the answer into statements and counts those that can be inferred from the contexts | 0–1 |
| | [`deepeval.faithfulness`](https://github.com/confident-ai/deepeval/tree/29dcf5f24397715a60348c1e41e7d416a3b2d6c8/deepeval/metrics/faithfulness) | Extracts truths from the contexts and claims from the answer, and penalizes claims that contradict them | 0–1 |
| | [`trulens.groundedness`](https://github.com/truera/trulens/blob/1f65a310cd5bdaef3ea7be76e98022f574cea39c/src/feedback/trulens/feedback/llm_provider.py#L3347) | Grades each answer sentence against the contexts | 0–3, normalized |
| | [`chaejeom.groundedness`](../src/chaejeom/metrics/chaejeom/groundedness.py) | Marks each statement and whether it is core to the question; rules set the level | 5 levels |
| Context relevance | [`ragas.context_relevance`](https://github.com/vibrantlabsai/ragas/tree/4ecab384fda829ca50bec3f07cc49589d756e172/src/ragas/metrics/collections/context_relevance) | Two judge prompts rate the contexts as a whole | 0–2, normalized |
| | [`deepeval.contextual_relevancy`](https://github.com/confident-ai/deepeval/tree/29dcf5f24397715a60348c1e41e7d416a3b2d6c8/deepeval/metrics/contextual_relevancy) | Extracts statements from each context and counts the relevant ones | 0–1 |
| | [`trulens.context_relevance`](https://github.com/truera/trulens/blob/1f65a310cd5bdaef3ea7be76e98022f574cea39c/src/feedback/trulens/feedback/llm_provider.py#L727) | Grades each chunk | 0–3, normalized |
| | [`chaejeom.context_relevance`](../src/chaejeom/metrics/chaejeom/context_relevance.py) | Marks each chunk as holding the answer, on topic, or irrelevant; rules set the level | 5 levels |
| Answer relevance | [`ragas.response_relevancy`](https://github.com/vibrantlabsai/ragas/tree/4ecab384fda829ca50bec3f07cc49589d756e172/src/ragas/metrics/collections/answer_relevancy) | Generates questions from the answer and compares them with the query by embedding similarity | −1–1 |
| | [`deepeval.answer_relevancy`](https://github.com/confident-ai/deepeval/tree/29dcf5f24397715a60348c1e41e7d416a3b2d6c8/deepeval/metrics/answer_relevancy) | Splits the answer into statements and counts the relevant ones | 0–1 |
| | [`trulens.answer_relevance`](https://github.com/truera/trulens/blob/1f65a310cd5bdaef3ea7be76e98022f574cea39c/src/feedback/trulens/feedback/llm_provider.py#L1121) | Grades the whole answer | 0–3, normalized |
| | [`chaejeom.answer_relevance`](../src/chaejeom/metrics/chaejeom/answer_relevance.py) | Marks how the answer responds; rules set the level | 5 levels |

Every score in the results is on 0–1, higher is better; the original scale is kept as `raw_score`. Run
`chaejeom list` to see the metrics and the inputs each one needs.

## Built for Korean

Asking an English-prompted judge to "answer in Korean" changes only the output language. Chaejeom prepares the whole
evaluation for Korean:

| Only asking for Korean output | Chaejeom |
|---|---|
| The judge reads English few-shot examples while judging Korean text | Few-shot examples are rewritten as Korean sentences, keeping the original number of examples and mix of verdicts |
| TruLens splits Korean answers with an English sentence tokenizer (nltk) | Sentences are split with a Korean morphological analyzer (kiwipiepy) |
| Explanations come back in mixed styles | Explanations use a consistent polite style; extracted statements use a plain declarative style |
| The same concept is translated differently by each framework | A shared [glossary](glossary.md) keeps terms consistent across the three frameworks |

## Upstream metrics

The RAGAS, DeepEval and TruLens metrics follow the upstream code at the commits listed in the
[README](../README.md#upstream-versions): prompts, procedures, verdict scales, aggregation formulas, defaults and edge
cases. Every change is recorded in the metric's source file and in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Their prompts are read-only in Chaejeom, so scores stay
comparable with what the original frameworks measure.

## Chaejeom metrics

The Chaejeom metrics look at the same three axes and score each sample on five levels: 0, 0.25, 0.5, 0.75 and 1.0.
The judge only marks what it can check, and code turns those marks into a level, so the same marks always give the
same score.

Their judge prompts combine what works in the upstream prompts:

| From | Rule |
|---|---|
| RAGAS | Split the answer into atomic statements without pronouns; an "it depends" answer that names no case is evasive |
| DeepEval | Tell statements missing from the contexts apart from statements that contradict them |
| TruLens | Skip greetings and other trivial sentences; quote the evidence; a related topic is not support; a chunk answers only if it matches every entity the question names (company, period, metric); a multi-part question is answered directly only if every part is |

| Metric | The judge marks | Levels |
|---|---|---|
| Groundedness | Each statement in the answer: supported, not in the context, or contradicted; and whether it is core to the question | 1.0 every statement supported<br>0.75 only non-core statements missing from the context<br>0.5 a core statement missing from the context<br>0.25 a statement contradicts the context<br>0 no supported core statement |
| Context relevance | Each chunk: whether it is about what the question asks, and whether it holds the answer | 1.0 a chunk holds the answer and no chunk is irrelevant<br>0.75 a chunk holds the answer; under half are irrelevant<br>0.5 a chunk holds the answer; half or more are irrelevant<br>0.25 no chunk holds the answer, but some are on topic<br>0 nothing relevant |
| Answer relevance | Whether the answer evades, says the information is not in the materials, addresses the same target, and answers directly | 1.0 answers directly<br>0.75 answers directly but adds unrelated content<br>0.5 gives only general conditions<br>0.25 answers a different aspect<br>0 off topic or evasive<br>no score: says the information is not in the materials |

### Safeguards

- **Quotes are verified.** Evidence the judge quotes must appear in the retrieved contexts, ignoring spacing,
  full-width characters and quote marks. Because judges often change a connective ending or skip the middle of a long
  sentence when quoting Korean, a quote also counts when at most two in-order pieces of one chunk cover 90% of it,
  provided every number in the quote appears in that chunk. Otherwise the statement counts as not in the context and
  the reason says so. When a supported statement's numbers do not appear in the quoted chunk, the verdict stands but is flagged
  "확인 필요" (needs review), because answers often compute values such as growth rates or rely on a period given
  only in a chunk header.
- **"Not in the materials" is checked.** When an answer says the information is not in the retrieved materials,
  groundedness checks the claim: the judge first looks for the asked value in the contexts. The statement is
  supported if the value is truly absent and contradicted if a chunk has it. Answer relevance does not score such
  answers, because it does not see the contexts. Both checks require the answer to really say so: answer relevance
  needs the judge to quote that sentence from the answer, and groundedness accepts the claim without evidence only
  when the statement itself says something is missing.
- **One question per axis.** When contexts disagree, a statement backed by any chunk is supported. Retrieving an
  outdated chunk is a context relevance problem, not a groundedness problem.
- **Contact details are checked.** "Please call 1588-0000" is checked against the contexts; a plain "please contact
  the help desk" is not judged.
- **No misleading scores.** An answer with no factual statement, such as "I don't know" or only a referral, gets no
  groundedness score. Its evasion is penalized by answer relevance instead.

### Domain files

The right judgment can depend on the domain. In a stock information service, an answer about HBM addresses a
question about memory chips, while an answer about HBM to a question about NAND does not. A domain file states such
rules per metric, in your words, and Chaejeom adds them word for word to that metric's judge prompt.

The service goes into the judge's role line, and the rules go into a "[이 도메인의 판정 기준]" block after the
procedure, which takes precedence where the two differ. Nothing else in the prompt changes, so the marks and the
five-level rules mean the same with or without a domain. Code inserts the text rather than an LLM rewriting the
prompt: in trials, a rewrite invented rules the user never gave and dropped unrelated built-in ones.

Domain rules decide what counts as the same target or as exact, never what is true: the items hold no values that
could act as answers, and facts are still judged from the retrieved contexts alone. Scores can therefore move in
either direction, toward what is right for the domain.

Create a domain file with `/domain` in the interactive terminal; see
[Configuration](configuration.md#domain-file). The Chaejeom prompts can also be revised in your own words with
`/prompt`; see [Configuration](configuration.md#prompt-file).

## Choosing metrics

| You want to | Use |
|---|---|
| Report numbers others can relate to RAGAS, DeepEval or TruLens | The upstream metrics: `preset: rag-triad` |
| Find which samples fail and why, with the same rules every time | The Chaejeom metrics, with a domain file |
| Evaluate a retriever on its own | Context relevance only: `axis: context_relevance`. Answers are not needed, and a domain file with `service` and `context_relevance` is enough |
| Evaluate a chatbot end to end | All 12: `preset: all`, the interactive default |

## Reading scores

The `Average` column is the mean of the RAGAS, DeepEval and TruLens metrics on each axis. The Chaejeom metrics have
their own column and are left out of the average, because their criteria depend on your domain. Read the average
together with the individual metrics.

### When the frameworks disagree

The frameworks ask different questions, so different scores on one axis usually tell you something about the answer:

| Pattern | What it usually means |
|---|---|
| Groundedness: DeepEval high, RAGAS low | The answer adds information the contexts do not have, without contradicting them. DeepEval penalizes only contradictions |
| Groundedness: every framework low | The answer contradicts the contexts or makes up its key facts |
| Context relevance: RAGAS high, the others low | At least one chunk is relevant, but much of what was retrieved is not. RAGAS judges the contexts as a whole |
| Answer relevance: DeepEval high, TruLens or Chaejeom low | The answer talks around the question or evades it. DeepEval counts on-topic statements |

Open the sample with `/show` in the interactive terminal to see the verdicts behind each number.

### Edge cases

| Situation | Result (as in the original framework) |
|---|---|
| RAGAS Faithfulness finds no statements | No score (`null`) |
| DeepEval Faithfulness or AnswerRelevancy finds no claims or statements | 1 |
| DeepEval ContextualRelevancy finds no statements | 0 |
| TruLens Groundedness has no sentences left after dropping trivial ones | 0 |
| RAGAS ResponseRelevancy | Uses cosine similarity as is, so it can occasionally be below 0 |
| Chaejeom Groundedness finds no factual statement | No score; the evasion is penalized by answer relevance |
| Chaejeom Answer relevance on an answer that says the information is not in the materials | No score, verdict `declined`; groundedness checks the claim |

A missing score (`null`) is different from 0 and is left out of means.
