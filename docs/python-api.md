# Python API

**English | [한국어](python-api.ko.md)**

```python
from chaejeom import EvalSample, evaluate

samples = [
    EvalSample(
        id="hr-01",
        query="재택근무는 일주일에 며칠까지 가능한가요?",
        contexts=["재택근무는 주 2일까지 신청할 수 있으며, 팀장 승인이 필요하다."],
        answer="재택근무는 팀장 승인을 받아 주 2일까지 할 수 있습니다.",
    )
]

result = evaluate(samples, metrics={"ragas": ["faithfulness"], "chaejeom": "all"})
print(result.by_axis["groundedness"])
result.to_json("result.json")
result.to_csv("result.csv")
```

Set `OPENAI_API_KEY` in your environment, or pass your own client.

## `evaluate` and `aevaluate`

```python
evaluate(samples, llm=None, **options) -> EvalResult
await aevaluate(samples, llm=None, **options) -> EvalResult
```

`evaluate` also works where an event loop is already running, such as Jupyter. In async code, use `aevaluate`.

| Argument | Default | Description |
|---|---|---|
| `samples` | | A list of `EvalSample` |
| `llm` | gpt-4.1-mini | The judge client; see [Clients](#clients) |
| `metrics` | | Metrics to run: `{"ragas": ["faithfulness"], "trulens": "all"}`, or a list such as `["ragas.*", {"deepeval.faithfulness": {"include_reason": False}}]` |
| `axis` | | Every metric on an axis: `"groundedness"`, `"context_relevance"`, `"answer_relevance"`, or a list |
| `preset` | | `"rag-triad"` for the 9 upstream metrics, `"all"` for all 12 |
| `embeddings` | text-embedding-3-large | The embedding client, created only when a selected metric needs it |
| `concurrency` | 4 | (sample, metric) pairs evaluated at the same time |
| `repeats` | 3 | Number of runs; results report the mean ± standard deviation across runs |
| `cache` | `True` | `True` caches LLM responses in `.chaejeom_cache/`, a string sets another folder, `False` disables it |
| `on_progress` | | Called as `on_progress(done, total)` after each evaluation |
| `label` | | A name for this run, stored in the result |

`metrics`, `axis` and `preset` can be combined. Metric options are listed in
[Configuration](configuration.md#metric-options). The Chaejeom metrics also take a domain file and a custom prompt
file:

```python
evaluate(samples, metrics=[{"chaejeom.groundedness": {"domain": "domains/finance.yaml", "prompt": "prompts/chaejeom.groundedness.yaml"}}])
```

An invalid API key, missing permission or unknown model stops the run with the provider's error instead of recording
the same failure for every sample. Other failures are recorded per metric and sample in `MetricResult.error`.

## Samples

```python
from chaejeom import Context, EvalSample

EvalSample(query="...", contexts=["...", "..."], answer="...")
EvalSample(id="hr-02", query="...", contexts=[Context(id="doc-12", text="...", rank=1)], answer="...", metadata={"retriever": "bm25"})
```

The fields and the RAGAS and DeepEval field names that are also accepted are described in
[Data format](data-format.md). To read a data file, use `chaejeom.data.load_samples(path)`.

## Results

`EvalResult` is a Pydantic model with the structure described in [Results](results.md).

| Attribute or method | Description |
|---|---|
| `summary` | Per-metric scores (`mean`, `std`, per-run `runs`) |
| `by_axis` | Axis × framework table, including `average` |
| `samples` | Per-sample scores and every `MetricResult` |
| `cost` | LLM calls, tokens and estimated cost for the whole run |
| `to_json(path)`, `to_csv(path)` | Save the result; both return the path |

Load a saved result with `EvalResult.model_validate_json(Path("result.json").read_text(encoding="utf-8"))`.

## Clients

```python
from chaejeom.embeddings import create_embeddings
from chaejeom.llm import create_llm

llm = create_llm("openai", "gpt-5-mini", reasoning_effort="low")
embeddings = create_embeddings("openai", "text-embedding-3-small")
result = evaluate(samples, llm=llm, embeddings=embeddings, preset="all")
```

| Option | Default | Description |
|---|---|---|
| `temperature` | 0.0 | For non-reasoning models |
| `reasoning_effort` | | For reasoning models; replaces `temperature` |
| `max_concurrency` | 8 | Concurrent calls to this model |
| `max_retries` | 5 | SDK retries on 429, 5xx and connection errors |
| `max_output_tokens` | 4096, or 16000 with `reasoning_effort` | Cuts off runaway responses |
| `api_key`, `base_url` | from the environment | Passed to the OpenAI client |

Only the `"openai"` provider is supported for now.
