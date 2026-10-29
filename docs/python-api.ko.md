# Python API

**[English](python-api.md) | 한국어**

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

환경 변수에 `OPENAI_API_KEY`를 설정하거나, 직접 만든 클라이언트를 넘깁니다. 라이브러리는 `.env` 파일을 읽지 않고,
읽는 것은 CLI뿐입니다. 키가 없으면 기본 클라이언트를 만들 때 평가를 시작하기도 전에 `OpenAIError`가 납니다.

## `evaluate`와 `aevaluate`

```python
evaluate(samples, llm=None, **options) -> EvalResult
await aevaluate(samples, llm=None, **options) -> EvalResult
```

`evaluate`는 Jupyter처럼 이벤트 루프가 이미 돌고 있는 곳에서도 동작합니다. 비동기 코드에서는 `aevaluate`를 씁니다.

| 인자 | 기본값 | 설명 |
|---|---|---|
| `samples` | | `EvalSample` 목록 |
| `llm` | gpt-4.1-mini | 평가 모델 클라이언트. [클라이언트](#클라이언트) 참고 |
| `metrics` | | 실행할 지표: `{"ragas": ["faithfulness"], "trulens": "all"}` 또는 `["ragas.*", {"deepeval.faithfulness": {"include_reason": False}}]` 같은 목록 |
| `axis` | | 축의 지표 전부: `"groundedness"`, `"context_relevance"`, `"answer_relevance"` 또는 그 목록 |
| `preset` | | `"rag-triad"`는 원본 지표 9개, `"all"`은 12개 전부 |
| `embeddings` | text-embedding-3-large | 임베딩 클라이언트. 고른 지표에 필요할 때만 만듦 |
| `concurrency` | 4 | 동시에 진행하는 평가 (샘플, 지표, 회차) 수 |
| `repeats` | 3 | 반복 횟수. 회차 간 평균과 표준편차를 냄 |
| `cache` | `True` | `True`면 `.chaejeom_cache/llm.sqlite`에 LLM 응답을 캐시, 문자열이면 그 폴더, `False`면 끔. 회차 번호가 캐시 키에 들어감 |
| `on_progress` | | 평가가 하나 끝날 때마다 `on_progress(done, total)`로 호출 |
| `label` | | 이 실행의 이름. 결과에 저장됨 |

`metrics`, `axis`, `preset`은 함께 써도 됩니다. 지표 옵션은 [설정](configuration.ko.md#지표-옵션)을 보세요. 채점
지표는 도메인 정보 파일과 수정본 프롬프트 파일도 받습니다. `prompts/chaejeom.groundedness.yaml` 같은 프롬프트
파일은 대화형 터미널의 `/prompt`가 만듭니다. 없는 경로를 주면 호출 전에 멈추고, 프롬프트 파일이 도메인 정보
파일보다 우선합니다.

```python
evaluate(samples, metrics=[{"chaejeom.groundedness": {"domain": "domains/finance.yaml"}}])
```

API 키가 틀렸거나, 권한이 없거나, 모델이 없으면 모든 샘플에 같은 실패를 남기지 않고 제공자의 오류로 실행을
멈춥니다. 그 밖의 실패는 지표와 샘플마다 `MetricResult.error`에 남습니다.

## 샘플

```python
from chaejeom import Context, EvalSample

EvalSample(query="...", contexts=["...", "..."], answer="...")
EvalSample(id="hr-02", query="...", contexts=[Context(id="doc-12", text="...", rank=1)], answer="...", metadata={"retriever": "bm25"})
```

필드와 함께 받는 RAGAS, DeepEval 필드 이름은 [데이터 형식](data-format.ko.md)을 보세요. 데이터 파일은
`chaejeom.data.load_samples(path)`로 읽습니다.

## 결과

`EvalResult`는 [결과](results.ko.md)에 적은 구조의 Pydantic 모델입니다.

| 속성이나 메서드 | 설명 |
|---|---|
| `summary` | 지표별 점수 (`mean`, `std`, 회차별 `runs`) |
| `by_axis` | `average`를 포함한 축별, 프레임워크별 점수표 |
| `samples` | 샘플별 점수와 모든 `MetricResult` |
| `cost` | 실행 전체의 LLM 호출, 토큰, 예상 비용 |
| `to_json(path)`, `to_csv(path)` | 결과 저장. 둘 다 경로를 돌려줌 |

저장한 결과는 `EvalResult.model_validate_json(Path("result.json").read_text(encoding="utf-8"))`로 다시 읽습니다.

## 클라이언트

```python
from chaejeom.embeddings import create_embeddings
from chaejeom.llm import create_llm

llm = create_llm("openai", "gpt-5-mini", reasoning_effort="low")
embeddings = create_embeddings("openai", "text-embedding-3-small")
result = evaluate(samples, llm=llm, embeddings=embeddings, preset="all")
```

`create_llm`은 아래 옵션을 받습니다. `create_embeddings`는 `api_key`와 `base_url`만 받습니다.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `temperature` | 0.0 | 일반 모델용 |
| `reasoning_effort` | | 추론 모델용. `temperature` 대신 씀 |
| `max_concurrency` | 8 | 이 모델로 동시에 보내는 호출 수 |
| `max_retries` | 5 | 429, 5xx, 연결 오류 때 SDK가 다시 시도하는 횟수 |
| `max_output_tokens` | 4096, `reasoning_effort`가 있으면 16000 | 끝없이 이어지는 응답을 끊음 |
| `max_attempts` | 3 | 응답이 형식 검증을 통과하지 못할 때 시도하는 횟수 |
| `api_key`, `base_url` | 환경 변수에서 | OpenAI 클라이언트에 그대로 넘어감 |

지금은 `"openai"` 제공자만 지원합니다.
