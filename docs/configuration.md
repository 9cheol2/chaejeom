# Configuration

**English | [한국어](configuration.ko.md)**

`chaejeom run --config` and `chaejeom -c` read a YAML config file. Every key is optional, except that `chaejeom run` needs at
least one of `metrics`, `axis` or `preset`; the interactive terminal starts with all 12 metrics when none is given.
Unknown keys and options are reported before anything runs. `/config save` in the interactive terminal writes your current settings in this format.

```yaml
judge:                          # default: openai gpt-4.1-mini
  provider: openai
  model: gpt-4.1-mini
  # temperature: 0.0            # non-reasoning models (default 0)
  # reasoning_effort: low       # reasoning models, instead of temperature (default low)
  # max_concurrency: 8          # concurrent calls to this model (default 8)
  # max_retries: 5              # SDK retries on 429, 5xx and connection errors (default 5)
  # max_output_tokens: 4096     # output cap (default 4096, 16000 for reasoning models)
  # max_attempts: 3             # tries when a response fails format validation (default 3)
  # base_url: https://...       # another OpenAI-compatible endpoint; api_key is also accepted

embedding:                      # default: openai text-embedding-3-large; used only when a metric needs embeddings
  provider: openai
  model: text-embedding-3-large

metrics:                        # per framework; "all" selects every metric of that framework
  ragas:
    - faithfulness
    - response_relevancy: {strictness: 3}
  deepeval:
    - faithfulness: {penalize_ambiguous_claims: true}
  trulens: all
  chaejeom: all
# axis: groundedness            # every metric on an axis: groundedness, context_relevance, answer_relevance
# preset: rag-triad             # the 9 RAGAS, DeepEval and TruLens metrics
# preset: all                   # all 12

runs: 3                         # repeat every evaluation; 2 or more reports mean and std (default 3)
concurrency: 4                  # evaluations (sample, metric, run) in flight at once (default 4)
cache: true                     # store and reuse LLM responses (default true)
cache_dir: .chaejeom_cache
language: en                    # interface language: en or ko (overrides the remembered one); judge explanations are always Korean

domain: domains/hr.yaml         # domain file for the Chaejeom metrics
domain_model:                   # model behind /domain and /prompt (default openai gpt-4.1-mini)
  provider: openai
  model: gpt-4.1-mini
prompts:                        # custom prompt files for the Chaejeom metrics
  chaejeom.groundedness: prompts/chaejeom.groundedness.yaml
```

## Models

Chaejeom currently supports the OpenAI API only, for the judge, the embedding model and the domain model. Put your
key in `OPENAI_API_KEY`, in a `.env` file in the working directory or in your environment. Values already set in the
environment take precedence over `.env`.

A model takes either `temperature` (non-reasoning models) or `reasoning_effort` (reasoning models), never both.
`max_output_tokens` only cuts off runaway responses; a normal verdict is far shorter. The judge and domain models also
accept `max_attempts`, `api_key` and `base_url`; the embedding model accepts only `api_key` and `base_url`.

The judge decides the scores, so compare results only when they were measured with the same judge. Result files
record the judge and embedding settings, and `chaejeom compare` warns when they differ.

## Selecting metrics

`metrics`, `axis` and `preset` can be combined; a metric selected more than once runs once. In `metrics`, give a
metric name alone or `{name: {option: value}}`. Axis names can also be written in Korean (`근거성`, `문맥 관련성`,
`답변 관련성`). `metrics` can also be a flat list of ids or patterns such as `ragas.*`, and `axis` can be a list.

Relative paths in `domain`, `prompts` and `cache_dir` are resolved against the working directory, not the folder of
the config file.

### Metric options

Defaults are those of the original framework.

| Metric | Option | Default | Description |
|---|---|---|---|
| `ragas.context_relevance` | `max_retries` | 5 | Attempts per judge prompt until a valid rating comes back |
| `ragas.response_relevancy` | `strictness` | 3 | Number of questions generated from the answer |
| `deepeval.faithfulness` | `include_reason` | true | Generate the score reason with the LLM (one extra call) |
| | `penalize_ambiguous_claims` | false | Count borderline verdicts as failures |
| | `truths_extraction_limit` | none | Maximum number of truths extracted from the contexts |
| `deepeval.contextual_relevancy` | `include_reason` | true | |
| `deepeval.answer_relevancy` | `include_reason` | true | |
| `trulens.groundedness` | `use_sent_tokenize` | true | Split sentences with kiwipiepy; `false` asks the LLM |
| | `filter_trivial_statements` | true | Drop sentences without substance, such as greetings, before scoring |
| `chaejeom.*` | `domain` | none | Domain file for this metric; overrides the top-level `domain` |
| | `prompt` | none | Custom prompt file for this metric; overrides `prompts` |

## Runs

LLM judges do not always return the same verdict for the same input, so every evaluation runs three times by default
and results report the mean and standard deviation across runs. `runs: 1` costs a third as much. `--runs` on the command
line takes precedence; the older name `repeats` still works. See [Results](results.md#repeated-runs) for how the
statistics are computed.

## Cache

Identical requests reuse the stored response, so re-running an evaluation or adding a metric to a finished run costs
nothing for the verdicts you already have.

| | |
|---|---|
| Key | Model, endpoint (`base_url`), temperature, reasoning effort, the full prompt and the run number. Any change triggers a new call |
| Repeated runs | The run number is part of the key, so every run gets fresh verdicts |
| What is stored | Only responses that pass format validation |
| Turning it off | `cache: false`, or `chaejeom run --no-cache` |
| Clearing it | Delete the cache folder |

## Domain file

A domain file adapts the Chaejeom metrics to your service. You state, per metric, how judging should differ in your
domain, such as which targets count as the same. Create one with `/domain` or write it by hand. Without one, the
Chaejeom metrics use the built-in prompts; the interactive terminal asks before running and `chaejeom run` prints a
warning.

```yaml
name: 금융 정보
service: 투자자가 상장사 실적, 공시, 증권사 리포트를 묻는 금융 정보 챗봇
groundedness: 실적 수치는 기간, 단위, 연결/별도 기준까지 문맥과 같아야 맞는 것으로 본다.
context_relevance: 메모리 반도체를 물으면 D램, 낸드, HBM을 다룬 조각도 관련 있다. 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다.
answer_relevance: 메모리 반도체를 물으면 D램, 낸드, HBM으로 답해도 같은 대상이다. 낸드를 물었는데 HBM으로 답하면 다른 대상이다.
```

| Key | Used by | Effect |
|---|---|---|
| `name` | none | Required. A name for the file, shown in the terminal; it does not change judging |
| `service` | all three | Goes into the judge's role line |
| `groundedness`, `context_relevance`, `answer_relevance` | that metric | Added with your wording unchanged, one sentence per line, as a "[이 도메인의 판정 기준]" block after the procedure. Where it differs from the procedure, it takes precedence |

Other keys are rejected. Empty keys leave the prompt as it is, and nothing else in the prompt changes; `/domain` and `/prompt` show the
resulting prompt. The items hold judging rules and types of information (`수수료율`), never values (`3%`), so the
evaluation stays reference-free; `/domain` refuses to save values that could act as answers. A domain can move scores
in either direction: it decides what counts as the same target or as exact, not what is true, which is still judged
from the retrieved contexts alone. Files in the earlier format (`critical_info`, `document_scope`, `expected_answer`)
must be created again.

## Prompt file

The Chaejeom prompts can be revised with `/prompt`: describe the change in your own words and the domain model revises
the prompt to match. The result is saved as a prompt file:

```yaml
metric: chaejeom.groundedness
requests:                       # requests so far, oldest first
- 한 문장에 사실이 여러 개 이어져 있으면 뒤쪽 사실도 모두 따로 진술로 뽑아 주세요.
template: |                     # the revised prompt; you can also edit it directly
  당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다.

  [평가 지표] 근거성: 답변의 내용이 문맥으로 뒷받침되는지 봅니다. ...
```

What the metric measures (the `[평가 지표]` line), the input slots (`{query}` and so on) and the output format
(`[출력 형식]`) must stay as they are, because the scoring rules read them; a file that changes them is refused when
loaded. Everything else, including the judgment examples, can change. Results measured with a custom prompt are marked
with `*` and record the prompt's fingerprint and requests. A prompt file takes precedence over the domain file for its
metric; with a domain set, `/prompt` starts from the domain's prompt. The RAGAS, DeepEval and TruLens prompts are
read-only.

## Data flow

| What | Sent to | When |
|---|---|---|
| Query, contexts, answer | The judge model | Every metric |
| The query, and the questions generated from the answer | The embedding model | RAGAS ResponseRelevancy only |
| Your domain description and prompt requests | The domain model | `/domain` and `/prompt` only |

Judge responses are stored in `.chaejeom_cache/` and results in `output/`, both as plain text
on your machine. If the embedding or domain model points to a different `base_url` than the judge, Chaejeom says so
before sending anything.
