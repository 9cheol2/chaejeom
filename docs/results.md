# Results

**English | [한국어](results.ko.md)**

Both the interactive terminal and `chaejeom run` save a JSON file and a CSV file in `output/`, named after the data
file and the time of the run, such as `output/sample_20261028-153012.json`. `chaejeom run --out FILE` sets another
name. In Python, `evaluate()` returns an `EvalResult` with the same
structure. The format is `schema_version: 1`.

## CSV

One row per sample, saved as UTF-8 with a BOM so Excel shows Korean correctly.

| Column | Content |
|---|---|
| `index`, `id`, `query` | Sample position, id and query |
| `meta.<key>` | Each key of the input `metadata` |
| `<metric id>` | The sample's score; with repeated runs, the mean across runs |
| `<metric id>.std` | Standard deviation across runs (repeated runs only) |
| `axis.<axis>` | Mean of the RAGAS, DeepEval and TruLens metrics on that axis |
| `errors` | Failed metrics with their run and error message |

Per-verdict details are only in the JSON file.

## JSON

```json
{
  "schema_version": 1,
  "chaejeom_version": "0.1.0.dev0",
  "created_at": "2026-10-23T09:00:00+00:00",
  "label": "retriever v1.3",
  "judge": {"client": "OpenAILLM", "model": "gpt-4.1-mini", "temperature": 0.0},
  "embedding": null,
  "metrics": {"ragas.faithfulness": {}, "deepeval.faithfulness": {"include_reason": true, "penalize_ambiguous_claims": false, "truths_extraction_limit": null}},
  "dataset": "3f2a9c1e7b04",
  "fingerprints": {"chaejeom.groundedness": {"domain": "a1b2c3d4e5f6", "prompt": "0f9e8d7c6b5a", "requests": ["..."]}},
  "repeats": 3,
  "summary": [
    {"metric_id": "deepeval.contextual_relevancy", "axis": "context_relevance",
     "mean": 0.69, "std": 0.05, "runs": [0.75, 0.67, 0.67], "scored": 6, "errors": 0, "dropped": 0}
  ],
  "by_axis": {
    "groundedness": {
      "ragas":    {"mean": 0.83, "std": 0.0, "runs": [0.83, 0.83, 0.83]},
      "deepeval": {"mean": 0.75, "std": 0.0, "runs": [0.75, 0.75, 0.75]},
      "average":  {"mean": 0.79, "std": 0.0, "runs": [0.79, 0.79, 0.79]}
    }
  },
  "cost": {"llm_calls": 52, "tokens": 34130, "cache_hits": 0, "input_tokens": 29025, "output_tokens": 5105, "usd": 0.0198},
  "samples": [
    {
      "index": 0,
      "id": "0",
      "query": "...",
      "metadata": {},
      "scores": {"ragas.faithfulness": {"mean": 0.67, "std": 0.0, "runs": [0.67, 0.67, 0.67]}},
      "results": [{"...": "MetricResult"}]
    }
  ]
}
```

| Field | Description |
|---|---|
| `label` | The run name given with `--label`, or `null` |
| `judge`, `embedding` | Models and settings used. Scores depend on the judge, so check these when comparing results |
| `metrics` | Metrics that ran, with the options actually used, including defaults |
| `dataset` | Short hash of the samples; equal values mean the same data |
| `fingerprints` | For the Chaejeom metrics: hashes of the domain file and custom prompt used, and the prompt requests |
| `repeats` | Number of runs |
| `summary` | Per metric: `mean`, `std` and per-run `runs`; `scored` results; `errors`; and `dropped`, samples left out of the run statistics because they lacked a score in some run |
| `by_axis` | Axis × framework table. `average` is the mean of the RAGAS, DeepEval and TruLens metrics on that axis |
| `cost` | Totals for the whole run, with the same fields as a metric result's `cost` |
| `samples` | Per sample: `id` and `metadata` from the input, per-metric `scores` across runs, and every `MetricResult` |

## MetricResult

```json
{
  "metric_id": "ragas.faithfulness",
  "source": {"framework": "ragas", "version": "v0.4.3", "commit": "4ecab38...", "method": "..."},
  "axis": "groundedness",
  "run": 1,
  "score": 0.67,
  "raw_score": 0.67,
  "raw_scale": "0~1 (직접 추론되는 진술의 비율)",
  "units": [
    {"type": "statement", "text": "...", "verdict": 0, "score": null, "reason": "...", "context_ids": []}
  ],
  "reason": "진술 3개 중 2개가 문맥에서 직접 추론됩니다.",
  "cost": {"llm_calls": 2, "tokens": 1840, "cache_hits": 0, "input_tokens": 1620, "output_tokens": 220, "usd": 0.000375},
  "error": null
}
```

| Field | Description |
|---|---|
| `source` | Framework, version and commit the metric was ported from, and a short description of its method |
| `run` | Which run this result belongs to, starting at 1 |
| `score` | 0 to 1, higher is better. `null` when it cannot be computed; this is different from 0 and is left out of means |
| `raw_score`, `raw_scale` | The score on the original framework's scale, and a description of that scale |
| `units` | Per-unit verdicts; see below |
| `reason` | Explanation of the score, in Korean |
| `cost` | LLM calls and tokens this metric used for this sample, responses reused from the cache, and the estimated cost in USD from the price table in `src/chaejeom/pricing.py`. Cached responses cost nothing; embedding calls are not counted |
| `error` | Why the metric failed, such as a missing input or an unreadable response. `cost` still counts the calls made before the failure |

### Units by metric

| Metric | `units.type` | `verdict` | `score` | `reason` | `context_ids` |
|---|---|---|---|---|---|
| `ragas.faithfulness` | statement | 0 / 1 | | verdict reason | |
| `ragas.context_relevance` | judge (two judge prompts) | 0 / 1 / 2 | | | |
| `ragas.response_relevancy` | generated_question | noncommittal 0 / 1 | cosine similarity | | |
| `deepeval.faithfulness` | truth (from contexts), claim (from the answer) | claims: yes / no / borderline | | for no and borderline | |
| `deepeval.contextual_relevancy` | statement (from a context) | yes / no | | for no | that context |
| `deepeval.answer_relevancy` | statement (from the answer) | yes / no / borderline | | for no and borderline | |
| `trulens.groundedness` | sentence (from the answer) | | 0–3 | supporting evidence | |
| `trulens.context_relevance` | chunk | | 0–3 | criteria and supporting evidence | that context |
| `trulens.answer_relevance` | none | | | | |
| `chaejeom.groundedness` | statement, with `core` | supported / unsupported / contradicted | | reason and the quoted context | the cited contexts |
| `chaejeom.context_relevance` | chunk | relevant / partial / irrelevant | | reason | that context |
| `chaejeom.answer_relevance` | judge (how the answer responds), statement (unrelated parts) | direct / indirect / other_aspect / off_topic / evasive / declined | | reason | |

Verdict values are kept as in the original frameworks.

## Repeated runs

| Value | How it is computed |
|---|---|
| Run score (`runs`) | Mean over the samples that got a score in every run; `dropped` counts the others |
| `mean` | Mean of the run scores |
| `std` | Sample standard deviation of the run scores; `null` with a single run |
| Axis average (`average`) | For each run, the mean of that axis's RAGAS, DeepEval and TruLens run scores; then their mean and standard deviation |
| Per-sample `scores` | That sample's per-run scores with their mean and standard deviation, useful for finding samples whose verdicts fluctuate |

Leaving out samples that failed in one run keeps a single error from looking like run-to-run variation. LLM calls and
cost grow with the number of runs.

## Cost estimate

Before a run, the CLI shows a rough estimate from token counts measured on the example data, scaled to the length of
your samples and, for metrics that judge chunks or answer sentences one by one, to how many there are. The estimate
assumes nothing is cached. Use `--limit` or `/run n` to measure the real cost on a few samples first.
