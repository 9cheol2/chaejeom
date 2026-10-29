# 결과

**[English](results.md) | 한국어**

대화형 터미널과 `chaejeom run` 모두 JSON 파일과 CSV 파일을 `output/` 폴더에 저장합니다. 이름은 데이터 파일 이름과
실행 시각으로 정해지며, 예를 들어 `output/sample_20261028-153012.json`입니다. `chaejeom run --out FILE`로 다른 이름을
줄 수 있습니다. 모든 지표가 실패해 점수가 하나도 없으면 파일을 저장하지 않고, `chaejeom run`은 종료 코드 1로
끝납니다. Python의 `evaluate()`는 같은 구조의 `EvalResult`를 돌려줍니다. 형식은
`schema_version: 1`입니다.

## CSV

샘플당 한 행이며, 엑셀에서 한글이 깨지지 않도록 BOM이 붙은 UTF-8로 저장합니다.

| 열 | 내용 |
|---|---|
| `index`, `id`, `query` | 샘플 순번, id, 질문 |
| `meta.<키>` | 입력 `metadata`의 키마다 한 열 |
| `<지표 id>` | 샘플의 점수. 반복 실행이면 회차 평균 |
| `<지표 id>.std` | 회차 간 표준편차 (반복 실행일 때만) |
| `axis.<축>` | 그 축의 RAGAS, DeepEval, TruLens 지표 평균 |
| `errors` | 실패한 지표와 회차, 오류 메시지 |

판정 단위별 내용은 JSON 파일에만 있습니다.

## JSON

```json
{
  "schema_version": 1,
  "chaejeom_version": "0.1.0.dev0",
  "created_at": "2026-10-23T09:00:00+00:00",
  "label": "검색기 v1.3",
  "judge": {"client": "OpenAILLM", "model": "gpt-4.1-mini", "temperature": 0.0},
  "embedding": null,
  "metrics": {"ragas.faithfulness": {}, "deepeval.faithfulness": {"include_reason": true, "penalize_ambiguous_claims": false, "truths_extraction_limit": null}},
  "dataset": "3f2a9c1e7b04",
  "fingerprints": {"chaejeom.groundedness": {"domain": "a1b2c3d4e5f6"}, "chaejeom.answer_relevance": {"prompt": "0f9e8d7c6b5a", "requests": ["..."]}},
  "repeats": 3,
  "summary": [
    {"metric_id": "deepeval.contextual_relevancy", "axis": "context_relevance",
     "mean": 0.70, "std": 0.05, "runs": [0.75, 0.67, 0.67], "scored": 6, "errors": 0, "dropped": 0}
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

| 필드 | 설명 |
|---|---|
| `label` | `--label`로 준 실행 이름. 없으면 `null` |
| `judge`, `embedding` | 채점에 쓴 모델과 설정. 점수는 평가 모델에 따라 달라지므로 결과를 비교할 때 확인 |
| `metrics` | 실행한 지표와 실제로 쓴 옵션(기본값 포함) |
| `dataset` | 샘플의 짧은 해시. 같으면 같은 데이터로 잰 결과 |
| `fingerprints` | 채점 지표가 쓴 도메인 정보 파일의 해시. 수정본 프롬프트가 도메인을 대신했으면 그 프롬프트의 해시와 수정 요청 |
| `repeats` | 반복 횟수 |
| `summary` | 지표별 `mean`, `std`, 회차별 `runs`, 점수가 난 결과 수 `scored`, 오류 수 `errors`, 어느 회차엔가 점수가 없어 회차 통계에서 뺀 샘플 수 `dropped` |
| `by_axis` | 축별, 프레임워크별 점수표. `average`는 그 축의 RAGAS, DeepEval, TruLens 지표 평균 |
| `cost` | 실행 전체의 합계. 필드는 지표 결과의 `cost`와 같음 |
| `samples` | 샘플별 결과. 입력의 `id`와 `metadata`, 지표별 회차 점수 `scores`, 모든 `MetricResult` |

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
  "cost": {"llm_calls": 2, "tokens": 1840, "cache_hits": 0, "input_tokens": 1620, "output_tokens": 220, "usd": 0.001},
  "error": null
}
```

| 필드 | 설명 |
|---|---|
| `source` | 지표를 옮겨 온 원본 프레임워크, 버전, 커밋과 방식 설명 |
| `run` | 몇 번째 회차의 결과인지 (1부터) |
| `score` | 0에서 1, 높을수록 좋음(`ragas.response_relevancy`는 드물게 0보다 작을 수 있음). 계산할 수 없으면 `null`이며, 0과 다르고 평균에서 빠짐 |
| `raw_score`, `raw_scale` | 원본 프레임워크 척도의 점수와 그 척도 설명 |
| `units` | 판정 단위별 결과. 아래 표 참고 |
| `reason` | 점수 설명 (한국어) |
| `cost` | 이 샘플에서 이 지표가 쓴 LLM 호출 수와 토큰, 캐시에서 재사용한 응답 수, `src/chaejeom/pricing.py`의 단가로 계산한 예상 비용(USD). 캐시 응답은 비용 없음. 임베딩 호출은 세지 않음. 단가표에 없는 모델은 0 |
| `error` | 필수 입력이 없거나 응답을 읽을 수 없는 등 실패한 이유. 실패 전까지 쓴 호출은 `cost`에 남음 |

### 지표별 판정 단위

| 지표 | `units.type` | `verdict` | `score` | `reason` | `context_ids` |
|---|---|---|---|---|---|
| `ragas.faithfulness` | statement | 0 / 1 | | 판정 이유 | |
| `ragas.context_relevance` | judge (판정 프롬프트 2개) | 0 / 1 / 2 | | | |
| `ragas.response_relevancy` | generated_question | noncommittal 0 / 1 | 코사인 유사도 | | |
| `deepeval.faithfulness` | truth (문맥에서), claim (답변에서) | claim만: yes / no / borderline | | no와 borderline일 때 | |
| `deepeval.contextual_relevancy` | statement (문맥에서) | yes / no | | no일 때 | 그 문맥 |
| `deepeval.answer_relevancy` | statement (답변에서) | yes / no / borderline | | no와 borderline일 때 | |
| `trulens.groundedness` | sentence (답변에서) | | 0에서 3 | 근거 | |
| `trulens.context_relevance` | chunk | | 0에서 3 | 근거 | 그 문맥 |
| `trulens.answer_relevance` | 없음 | | | | |
| `chaejeom.groundedness` | statement. `core` 포함 | supported / unsupported / contradicted | | 이유와 인용한 문맥 문장 | 인용한 문맥 |
| `chaejeom.context_relevance` | chunk | relevant / partial / irrelevant | | 이유 | 그 문맥 |
| `chaejeom.answer_relevance` | judge (답변이 응한 방식), statement (관계없는 부분) | judge: direct / indirect / other_aspect / off_topic / evasive / declined. statement: irrelevant | | 이유 (judge만) | |

판정 값은 원본 프레임워크의 값을 그대로 둡니다.

## 반복 실행

| 값 | 계산 방식 |
|---|---|
| 회차 점수 (`runs`) | 모든 회차에서 점수가 난 샘플의 평균. 나머지는 `dropped`로 셈 |
| `mean` | 회차 점수의 평균 |
| `std` | 회차 점수의 표본 표준편차. 한 번만 돌리면 `null` |
| 축 평균 (`average`) | 회차마다 그 축의 RAGAS, DeepEval, TruLens 회차 점수를 평균한 뒤, 그 값들의 평균과 표준편차 |
| 샘플별 `scores` | 그 샘플의 회차별 점수와 평균, 표준편차. 판정이 흔들리는 샘플을 찾을 때 씀 |

한 회차에서만 실패한 샘플을 빼서, 오류 하나가 회차 간 흔들림처럼 보이지 않게 합니다. 반복 횟수만큼 LLM 호출과
비용이 늘어납니다.

## 예상 비용

실행 전에 보여 주는 예상 비용은 평가 모델의 단가를 알 때만 나옵니다. 예제 데이터에서 잰 토큰 수를 바탕으로, 내
샘플의 길이와 (호출이나 출력이 조각, 답변 문장 수에 따라 늘어나는 지표는) 그 개수에 맞춰 늘린 대략적인 값입니다. 캐시를 쓰지 않는다고 보고 계산합니다. 실제 비용은
`--limit`이나 `/run n`으로 몇 개만 먼저 돌려 확인하세요.
