# Data format

**English | [한국어](data-format.ko.md)**

Chaejeom reads JSONL (one sample per line), a JSON file holding a list of samples, or CSV (one sample per row), in
UTF-8. CSV files saved by Korean Excel (CP949) are read too.

## Fields

```jsonl
{"query": "How many days a week can I work from home?", "contexts": ["Remote work can be requested up to 2 days a week.", "The cafeteria opens at 11:30."], "answer": "Up to 2 days a week."}
{"id": "hr-002", "query": "...", "contexts": [{"id": "doc-12", "text": "..."}], "answer": "...", "metadata": {"retriever": "bm25"}}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | The user question |
| `contexts` | list of strings, or of `{id, text, rank}` | Retrieved documents, in rank order. `id` and `rank` are optional and default to `c1, c2, ...` and `1, 2, ...` |
| `answer` | string | The answer to evaluate |
| `id` | string or number | Optional. Identifies the sample in results and in `chaejeom compare`; defaults to its position |
| `metadata` | object | Optional. Copied to the results as is |

Every field is optional. When a sample lacks a field a metric needs, only that metric records an error for that
sample; the rest keep running.

### Inputs each metric needs

| Metric | query | contexts | answer | embeddings |
|---|---|---|---|---|
| `ragas.faithfulness` | ✓ | ✓ | ✓ | |
| `ragas.context_relevance` | ✓ | ✓ | | |
| `ragas.response_relevancy` | ✓ | | ✓ | ✓ |
| `deepeval.faithfulness` | ✓ | ✓ | ✓ | |
| `deepeval.contextual_relevancy` | ✓ | ✓ | | |
| `deepeval.answer_relevancy` | ✓ | | ✓ | |
| `trulens.groundedness` | | ✓ | ✓ | |
| `trulens.context_relevance` | ✓ | ✓ | | |
| `trulens.answer_relevance` | ✓ | | ✓ | |
| `chaejeom.groundedness` | ✓ | ✓ | ✓ | |
| `chaejeom.context_relevance` | ✓ | ✓ | | |
| `chaejeom.answer_relevance` | ✓ | | ✓ | |

`chaejeom list` prints the same table.

## Field names from other frameworks

Datasets prepared for RAGAS or DeepEval work as is:

| Chaejeom | RAGAS | DeepEval |
|---|---|---|
| `query` | `user_input` | `input` |
| `contexts` | `retrieved_contexts` | `retrieval_context` |
| `answer` | `response` | `actual_output` |

Two kinds of extra fields are accepted with a notice instead of an error:

| Field | What happens |
|---|---|
| Ground-truth fields: `reference`, `reference_contexts`, `ground_truth`, `ground_truths`, `expected_output`, `expected_answer`, `context` (DeepEval's ideal context), `golden_answer`, `reference_answer` | Ignored, because every metric is reference-free |
| Any other field, such as `user_id` or `timestamp` | Moved into `metadata`, so it appears in the results |

## CSV

A header row, then one sample per row. Put each retrieved document in its own `context_1`, `context_2`, ... column;
empty cells are skipped. A `contexts` column holding a JSON list (`["...", "..."]`) also works, and any other value in
it is read as a single context, so a document such as `[공지] ...` is safe. Columns named `metadata.<key>` (or
`meta.<key>`, as in the result CSV) go into `metadata`.

```csv
id,query,context_1,context_2,answer,metadata.case
hr-01,How many days a week can I work from home?,Remote work can be requested up to 2 days a week.,The cafeteria opens at 11:30.,Up to 2 days a week.,correct
```

[examples/samples.csv](../examples/samples.csv) holds the same samples as
[examples/samples.jsonl](../examples/samples.jsonl).

## Format errors

Loading stops with a message that names the problem and shows the expected format when:

| Problem | Example |
|---|---|
| The extension is not `.jsonl`, `.json` or `.csv` | `samples.txt` |
| The file is not UTF-8 (or, for CSV, CP949) | A JSONL file saved as CP949 |
| A line is not valid JSON | A line cut in the middle |
| A CSV row has more cells than the header | An unquoted comma inside a cell |
| A `.json` file does not hold a list | `{"query": ...}` instead of `[{"query": ...}]` |
| A sample is not an object | `"just text"` |
| A sample has none of `query`, `contexts`, `answer` | Only `id` and `metadata` |
| A value has the wrong type | `contexts` given as a single string |
