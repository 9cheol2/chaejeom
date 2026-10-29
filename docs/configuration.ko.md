# 설정

**[English](configuration.md) | 한국어**

`chaejeom run --config`와 `chaejeom -c`는 YAML 설정 파일을 읽습니다. 모든 키는 생략할 수 있고, 모르는 키나 옵션은
실행 전에 알려 줍니다. 대화형 터미널의 `/config save`는 지금 설정을 이 형식으로 저장합니다.

```yaml
judge:                          # 기본: openai gpt-4.1-mini
  provider: openai
  model: gpt-4.1-mini
  # temperature: 0.0            # 일반 모델 (기본 0)
  # reasoning_effort: low       # 추론 모델. temperature 대신 씀 (기본 low)
  # max_concurrency: 8          # 이 모델로 동시에 보내는 호출 수 (기본 8)
  # max_retries: 5              # 429, 5xx, 연결 오류 때 SDK 가 다시 시도하는 횟수 (기본 5)
  # max_output_tokens: 4096     # 출력 상한 (기본 4096, 추론 모델은 16000)
  # base_url: https://...       # 그 밖의 키는 클라이언트에 그대로 넘어감

embedding:                      # 기본: openai text-embedding-3-large. 임베딩이 필요한 지표를 고를 때만 쓰임
  provider: openai
  model: text-embedding-3-large

metrics:                        # 프레임워크별로 고르기. "all" 이면 그 프레임워크의 지표 전부
  ragas:
    - faithfulness
    - response_relevancy: {strictness: 3}
  deepeval:
    - faithfulness: {penalize_ambiguous_claims: true}
  trulens: all
  chaejeom: all
# axis: 근거성                   # 축의 지표 전부: 근거성, 문맥 관련성, 답변 관련성
# preset: rag-triad             # RAGAS, DeepEval, TruLens 지표 9개
# preset: all                   # 12개 전부

runs: 3                         # 같은 평가를 반복할 횟수. 2 이상이면 평균 ± 표준편차 (기본 3)
concurrency: 4                  # 동시에 평가하는 (샘플, 지표) 쌍의 수 (기본 4)
cache: true                     # LLM 응답을 저장해 재사용 (기본 true)
cache_dir: .chaejeom_cache
language: en                    # 화면 언어: en 또는 ko. 판정 설명은 언제나 한국어

domain: domains/hr.yaml         # 채점 지표에 쓸 도메인 정보 파일
domain_model:                   # /domain, /prompt 에 쓰는 모델 (기본 openai gpt-4.1-mini)
  provider: openai
  model: gpt-4.1-mini
prompts:                        # 채점 지표의 수정본 프롬프트 파일
  chaejeom.groundedness: prompts/chaejeom.groundedness.yaml
```

## 모델

평가 모델, 임베딩 모델, 도메인 정리 모델 모두 지금은 OpenAI API만 지원합니다. 키는 실행 폴더의 `.env` 파일이나 환경
변수의 `OPENAI_API_KEY`에 넣습니다. 환경 변수에 이미 있는 값이 `.env`보다 우선합니다.

한 모델에는 `temperature`(일반 모델)와 `reasoning_effort`(추론 모델) 중 하나만 씁니다. `max_output_tokens`는 끝없이
이어지는 응답을 끊는 상한일 뿐이고, 정상 판정은 이보다 훨씬 짧습니다. `provider`와 `model` 외의 키는 클라이언트에
그대로 넘어갑니다.

점수는 평가 모델이 정하므로, 같은 평가 모델로 잰 결과끼리만 비교하세요. 결과 파일에는 평가 모델과 임베딩 모델의
설정이 기록되고, 다르면 `chaejeom compare`가 경고합니다.

## 지표 고르기

`metrics`, `axis`, `preset`은 함께 써도 되고, 겹치는 지표는 한 번만 실행됩니다. `metrics`에는 지표 이름만 쓰거나
`{이름: {옵션: 값}}`으로 옵션을 함께 줍니다. 축 이름은 영어(`groundedness`, `context_relevance`,
`answer_relevance`)로도 쓸 수 있습니다.

### 지표 옵션

기본값은 원본 프레임워크의 기본값입니다.

| 지표 | 옵션 | 기본값 | 설명 |
|---|---|---|---|
| `ragas.context_relevance` | `max_retries` | 5 | 올바른 점수가 나올 때까지 판정 프롬프트마다 시도하는 횟수 |
| `ragas.response_relevancy` | `strictness` | 3 | 답변에서 만들 질문의 수 |
| `deepeval.faithfulness` | `include_reason` | true | 점수 이유를 LLM으로 생성 (호출 1회 추가) |
| | `penalize_ambiguous_claims` | false | 애매한 판정도 실패로 셈 |
| | `truths_extraction_limit` | 없음 | 문맥에서 뽑을 사실의 최대 개수 |
| `deepeval.contextual_relevancy` | `include_reason` | true | |
| `deepeval.answer_relevancy` | `include_reason` | true | |
| `trulens.groundedness` | `use_sent_tokenize` | true | kiwipiepy로 문장 분리. `false`면 LLM에게 맡김 |
| | `filter_trivial_statements` | true | 인사말처럼 내용 없는 문장을 빼고 채점 |
| `chaejeom.*` | `domain` | 없음 | 이 지표에 쓸 도메인 정보 파일. 최상위 `domain`보다 우선 |
| | `prompt` | 없음 | 이 지표에 쓸 수정본 프롬프트 파일. `prompts`보다 우선 |

## 반복 실행

LLM 판정은 같은 입력에도 결과가 조금씩 달라질 수 있어서, 기본으로 모든 평가를 세 번 돌려 회차 간 평균 ±
표준편차를 보여 줍니다. `runs: 1`이면 비용이 3분의 1이 됩니다. 명령줄의 `--runs`가 우선하고, 예전 이름 `repeats`도
됩니다. 통계를 내는 방식은 [결과](results.ko.md#반복-실행)를 보세요.

## 캐시

같은 요청은 저장한 응답을 다시 쓰므로, 평가를 다시 돌리거나 끝난 평가에 지표를 하나 더해도 이미 받은 판정에는
비용이 들지 않습니다.

| | |
|---|---|
| 키 | 모델, temperature, reasoning effort, 프롬프트 전체, 회차 번호. 하나라도 바뀌면 새로 호출 |
| 반복 실행 | 회차 번호가 키에 들어가므로 회차마다 새 판정을 받음 |
| 저장하는 것 | 형식 검증을 통과한 응답만 |
| 끄기 | `cache: false` 또는 `chaejeom run --no-cache` |
| 지우기 | 캐시 폴더를 삭제 |

## 도메인 정보 파일

도메인 정보 파일은 채점 지표를 서비스에 맞춥니다. 이 도메인에서 판정이 어떻게 달라야 하는지, 예를 들어 무엇을 같은
대상으로 볼지를 지표마다 적습니다. `/domain`으로 만들거나 직접 씁니다. 파일이 없으면 채점 지표는 기본 프롬프트로
판정하며, 대화형 터미널은 실행 전에 묻고 `chaejeom run`은 경고를 보여 줍니다.

```yaml
name: 금융 정보
service: 투자자가 상장사 실적, 공시, 증권사 리포트를 묻는 금융 정보 챗봇
groundedness: 실적 수치는 기간, 단위, 연결/별도 기준까지 문맥과 같아야 맞는 것으로 본다.
context_relevance: 메모리 반도체를 물으면 D램, 낸드, HBM을 다룬 조각도 관련 있다. 낸드와 HBM처럼 하위 항목끼리는 다른 대상이다.
answer_relevance: 메모리 반도체를 물으면 D램, 낸드, HBM으로 답해도 같은 대상이다. 낸드를 물었는데 HBM으로 답하면 다른 대상이다.
```

| 키 | 쓰는 지표 | 효과 |
|---|---|---|
| `service` | 세 지표 모두 | 판정 모델의 역할 문장에 들어감 |
| `groundedness`, `context_relevance`, `answer_relevance` | 해당 지표 | [절차] 뒤에 "[이 도메인의 판정 기준]"으로 글자 그대로, 한 문장씩 줄을 나눠 들어감. [절차]와 다르면 이 기준을 따름 |

빈 키는 프롬프트를 바꾸지 않고, 프롬프트의 나머지도 바뀌지 않습니다. 결과 프롬프트는 `/domain`과 `/prompt`에서 볼
수 있습니다. 항목에는 판정 기준과 정보의 종류(`수수료율`)만 적고 값(`3%`)은 적지 않으므로 평가는 레퍼런스 프리로
유지됩니다. 정답이 될 수 있는 값이 있으면 `/domain`이 저장하지 않습니다. 도메인은 점수를 양쪽으로 움직일 수
있습니다. 무엇을 같은 대상으로 보고 무엇을 정확히 볼지를 정할 뿐, 무엇이 사실인지는 늘 검색된 문맥만으로
판단합니다. 예전 형식(`critical_info`, `document_scope`, `expected_answer`)의 파일은 새로 만들어야 합니다.

## 프롬프트 파일

채점 지표의 프롬프트는 `/prompt`에서 고칠 수 있습니다. 바꾸고 싶은 점을 적으면 도메인 정리 모델이 그에 맞게
프롬프트를 고치고, 결과는 프롬프트 파일로 저장됩니다.

```yaml
metric: chaejeom.groundedness
requests:                       # 지금까지의 요청, 오래된 것부터
- 한 문장에 사실이 여러 개 이어져 있으면 뒤쪽 사실도 모두 따로 진술로 뽑아 주세요.
template: |                     # 고친 프롬프트. 여기서 직접 고쳐도 됨
  당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다.

  [평가 지표] 근거성: 답변의 내용이 문맥으로 뒷받침되는지 봅니다. ...
```

지표가 재는 것(`[평가 지표]` 줄), 입력 자리(`{query}` 등), 출력 형식(`[출력 형식]`)은 점수 규칙이 읽는 부분이라
그대로 두어야 하며, 이를 바꾼 파일은 불러올 때 거부합니다. 판정 예시를 포함한 나머지는 바꿀 수 있습니다. 수정본
프롬프트로 잰 결과에는 `*` 표시가 붙고, 프롬프트의 지문과 요청이 기록됩니다. 프롬프트 파일은 그 지표에서 도메인
정보 파일보다 우선하며, 도메인이 설정되어 있으면 `/prompt`는 도메인 프롬프트에서 시작합니다. RAGAS, DeepEval,
TruLens 프롬프트는 고칠 수 없습니다.

## 데이터 흐름

| 무엇을 | 어디로 | 언제 |
|---|---|---|
| 질문, 문맥, 답변 | 평가 모델 | 모든 지표 |
| 질문과 답변, 생성한 질문 | 임베딩 모델 | RAGAS ResponseRelevancy만 |
| 도메인 설명, 프롬프트 수정 요청 | 도메인 정리 모델 | `/domain`, `/prompt`만 |

판정 응답은 `.chaejeom_cache/`에, 결과는 `output/`에 내 컴퓨터에 평문으로 저장됩니다.
임베딩 모델이나 도메인 정리 모델의 `base_url`이 평가 모델과 다르면, 보내기 전에 알려 줍니다.
