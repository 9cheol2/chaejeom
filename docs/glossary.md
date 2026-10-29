# 용어 대역표

9개 지표의 원본 프롬프트를 한국어로 옮길 때 쓰는 기준입니다.
원본: Ragas v0.4.3, DeepEval 4.3.1, TruLens 2.16.0 (커밋은 THIRD_PARTY_NOTICES.md 참고)

## 1. 번역 원칙

| 원칙 | 내용 |
|---|---|
| 1:1 대응 | 원문에서 다른 단어는 번역에서도 다른 단어로 옮긴다. 예: answer 는 답변, response 는 응답 |
| 프레임워크별 용어 유지 | 같은 대상이라도 프레임워크마다 부르는 이름이 다르면 그 차이를 살린다. 예: RAGAS question, DeepEval input, TruLens USER QUERY |
| 의미 우선 | 직역이 어색하면 뜻을 살려 옮기되, 판정 기준을 넓히거나 좁히지 않는다 |
| 인칭 유지 | 원문이 2인칭이면 "당신은 ...입니다", 1인칭이면 "저는 ...하겠습니다"로 옮긴다 (RAGAS ContextRelevance 두 번째 판정 프롬프트가 1인칭) |
| 문체 | 지시문은 "~하세요" 체로 통일한다 |
| 출력 문체 | 판정 이유와 설명, few-shot 예시의 이유는 "~습니다" 체 존댓말. 진술, 주장, 사실 같은 판정 단위는 원본처럼 "~이다" 체 (다음 단계에서 글자 그대로 다시 받아 적기 때문). 예시 문맥은 실제 문서처럼 "~한다" 체. 원본에 이유 예시가 없는 프롬프트에는 문체 지시 한 줄을 넣는다 (`src/chaejeom/metrics/style.py`) |
| 강조 | 원문의 대문자 강조(MUST, STRICTLY, ONLY, NEVER)는 "반드시", "오직", "절대" 같은 한국어 강조어로 옮긴다. 원문에 있는 `**` 구분선은 그대로 둔다 |
| 키 병기 | 본문에서 JSON 키를 가리키는 말은 처음 한 번 "한국어(영어 키)"로 병기한다. 예: 판정(verdict) |
| few-shot 예시 | 한국어로 새로 쓰되 원본 예시의 개수와 판정 분포를 유지한다. 예: RAGAS Faithfulness 판정 예시는 진술 4개 중 1이 1개, 0이 3개 |

## 2. 번역하지 않는 것

| 대상 | 예 | 이유 |
|---|---|---|
| JSON 키 | `statements`, `verdict`, `reason`, `claims`, `truths`, `verdicts`, `statement`, `rating`, `question`, `noncommittal`, `criteria`, `supporting_evidence`, `score` | 구조화 출력 파싱 |
| 판정 라벨 | `yes`, `no`, `borderline`, `0`, `1`, `2`, `3` | 집계식이 이 값을 그대로 씀 |
| TruLens 출력 라벨 | `Criteria:`, `Supporting Evidence:`, `Score:` | 응답에서 이 문자열을 찾아 파싱함. JSON 키와 같은 기계용 표시로 보고 원본 파싱 로직을 그대로 쓰기 위해 영어 유지. 라벨 뒤 내용은 한국어 |
| 특수 값 | `NOTHING FOUND`, `ABSTENTION` | TruLens Groundedness 의 supporting_evidence 값 |
| 템플릿 변수 | `{{ claims }}`, `{premise}`, `{max_score}` 등 | 코드에서 치환 |
| 지표 이름 | Faithfulness, ContextRelevance, ResponseRelevancy, ContextualRelevancy, AnswerRelevancy, Groundedness, Context Relevance, Answer Relevance | 원본 지표를 가리키는 고유 이름 |

## 3. 평가 대상

| 원어 | 번역 | 뜻 | 쓰이는 곳 |
|---|---|---|---|
| question | 질문 | 사용자가 한 질문 | RAGAS Faithfulness, ContextRelevance |
| answer | 답변 | 평가할 RAG 답변 | RAGAS Faithfulness, ResponseRelevancy |
| response | 응답 | 평가할 RAG 답변 | RAGAS ResponseRelevancy 입력 필드, TruLens RESPONSE |
| input | 입력 | 사용자 입력 | DeepEval AnswerRelevancy, ContextualRelevancy |
| actual output | 실제 출력 | 평가할 AI 출력 | DeepEval |
| AI output | AI 출력 | 평가할 AI 출력 | DeepEval Faithfulness |
| text | 텍스트 | 분해할 대상 글 | DeepEval |
| context | 문맥 | 검색된 문서 | 공통 |
| retrieval context | 검색 문맥 | 검색된 문서 | DeepEval |
| SOURCE | 근거 자료 | 검색된 문서 | TruLens Groundedness |
| STATEMENT | 진술 | 판정할 답변 문장 | TruLens Groundedness |
| USER QUERY | 사용자 질의 | 사용자 질문 | TruLens Context Relevance |
| SEARCH RESULT | 검색 결과 | 검색된 문서 조각 | TruLens Context Relevance |
| PROMPT | 프롬프트 | 에이전트에 들어간 입력 | TruLens Answer Relevance |

TruLens 의 대문자 라벨은 번역한 뒤에도 시스템 프롬프트와 사용자 프롬프트에서 같은 한국어 라벨로 맞춘다. 예: `USER QUERY:` 는 `사용자 질의:`

## 4. 판정 단위

| 원어 | 번역 | 뜻 | 쓰이는 곳 |
|---|---|---|---|
| statement | 진술 | 답변이나 문맥을 쪼갠 단위 | RAGAS Faithfulness, DeepEval AnswerRelevancy, ContextualRelevancy, TruLens |
| claim | 주장 | 답변에서 뽑은 사실 단위 | DeepEval Faithfulness |
| truth | 사실 | 문맥에서 뽑은 사실 단위 | DeepEval Faithfulness |
| fact | 사실 정보 | 문맥에 담긴 정보 | DeepEval Faithfulness |
| sentence | 문장 | 문장 분리 단위 | RAGAS, TruLens |
| contradiction | 모순 | 문맥과 어긋나는 주장 | DeepEval Faithfulness |
| irrelevant statement | 관련 없는 진술 | 질문과 무관한 진술 | DeepEval |

## 5. 판정과 척도

| 원어 | 번역 | 뜻 | 쓰이는 곳 |
|---|---|---|---|
| verdict | 판정 | 단위별 판정 결과 | 공통 |
| reason | 이유 | 판정 근거 설명 | 공통 |
| score | 점수 | 최종 또는 단위 점수 | 공통 |
| relevance score | 관련성 점수 | RAGAS 0/1/2 점수 | RAGAS ContextRelevance |
| criteria | 기준 | 채점 기준 | TruLens |
| supporting evidence | 뒷받침 근거 | 점수를 매긴 근거 문장 | TruLens |
| faithfulness | 충실성 | 문맥에 충실한 정도 | RAGAS, DeepEval 본문 |
| groundedness | 근거성 | 근거 자료가 뒷받침하는 정도 | TruLens, 축 이름 |
| relevance | 관련성 | 질문과 맞닿은 정도 | 공통, 축 이름 |
| relevant / irrelevant | 관련 있는 / 관련 없는 | | 공통 |
| directly inferred | 직접 추론할 수 있는 | 문맥만으로 이끌어 낼 수 있음 | RAGAS Faithfulness |
| contradict | 모순되다 | 문맥과 어긋남 | DeepEval Faithfulness |
| agree with | 일치하다 | 문맥과 맞음 | DeepEval Faithfulness |
| partially | 부분적으로 | | RAGAS ContextRelevance |
| prior knowledge | 사전 지식 | 모델이 원래 알던 지식 | 공통 |
| noncommittal | 회피성 | 답을 피하는 성질 | RAGAS ResponseRelevancy |
| evasive | 회피하는 | | RAGAS ResponseRelevancy |
| vague | 모호한 | | RAGAS ResponseRelevancy |
| ambiguous | 애매한 | | RAGAS ResponseRelevancy, DeepEval borderline 설명 |
| substantive | 실질적인 | 내용이 있는 | RAGAS ResponseRelevancy, TruLens Trivial |
| abstention | 답변 유보 | "모르겠습니다" 같은 응답 | TruLens Groundedness |
| trivial pleasantries | 의례적인 인사말 | | TruLens Trivial |
| stylistic | 문체적인 | 내용 없이 형식만 있는 | TruLens Trivial |
| entailment | 함의 | 근거 자료가 진술을 함축함 | TruLens Groundedness |
| information overlap | 정보 겹침 | | TruLens Groundedness |
| false positive | 거짓 양성 | 근거가 없는데 높은 점수를 줌 | TruLens Groundedness |
| full mark | 만점 | | TruLens Context Relevance |
| intermediate score | 중간 점수 | | TruLens Context Relevance |

### 지표를 옮기며 추가한 용어

| 원어 | 번역 | 쓰이는 곳 |
|---|---|---|
| rating | 등급 | RAGAS ContextRelevance 필드 설명 (relevance score 의 "관련성 점수"와 구분) |
| Question / Context (대문자) | 질문(Question) / 문맥(Context) | RAGAS ContextRelevance |
| generated question | 역질문 | RAGAS ResponseRelevancy |
| coherent | 앞뒤가 맞는 | DeepEval Faithfulness |
| undisputed | 논란의 여지가 없는 | DeepEval Faithfulness |
| factual | 사실에 기반한 | DeepEval Faithfulness |
| factually correct | 사실로서 맞는 | DeepEval Faithfulness |
| cherry picked | 일부만 골라낸 | DeepEval Faithfulness |
| high level information | 상위 수준의 정보 | DeepEval ContextualRelevancy |
| supporting information | 보조 정보 | DeepEval AnswerRelevancy |
| parseable JSON | 파싱 가능한 JSON | DeepEval |
| (Ambiguous) | (애매함) | DeepEval Faithfulness 이유 생성 |
| entity | 개체 | TruLens Context Relevance |
| tangentially related | 간접적으로 관련된 | TruLens Context Relevance |
| search phrase | 검색어, 검색 문장 | TruLens Context Relevance |
| rubric | 채점 기준표 | TruLens Answer Relevance |

## 6. 판정자 역할

| 원어 | 번역 | 쓰이는 곳 |
|---|---|---|
| expert | 전문가 | RAGAS ContextRelevance |
| classifier | 분류기 | TruLens Groundedness |
| grader | 채점자 | TruLens Context Relevance, Answer Relevance |
| rater | 평가자 | TruLens Context Relevance (CoT 프롬프트) |
| judge (units.type) | 판정 프롬프트 | RAGAS ContextRelevance 의 판정 프롬프트 2개 |

## 7. 프롬프트 틀 표현

| 원문 | 번역 | 쓰이는 곳 |
|---|---|---|
| Example 1 / Input / Output | 예시 1 / 입력 / 출력 | RAGAS 프롬프트 틀 |
| --------EXAMPLES----------- | --------예시----------- | RAGAS 프롬프트 틀 |
| Now perform the same with the following input | 이제 다음 입력에 대해 같은 작업을 수행하세요 | RAGAS 프롬프트 틀 |
| Please return the output in a JSON format that complies with the following schema as specified in JSON Schema | 다음 JSON Schema 를 따르는 JSON 형식으로 출력하세요 | RAGAS 프롬프트 틀 |
| Example / Example JSON / Example Text | 예시 / 예시 JSON / 예시 텍스트 | DeepEval |
| ===== END OF EXAMPLE ====== | ===== 예시 끝 ===== | DeepEval |
| IMPORTANT: | 중요: | DeepEval |
| Expected JSON format: | 출력 JSON 형식: | DeepEval |
| JSON: | JSON: | DeepEval (그대로) |
| Never elaborate. | 부연 설명은 절대 하지 마세요. | TruLens |
| Respond only as a number from ... | ... 사이의 숫자로만 답하세요. | TruLens |
| Think step by step | 단계별로 생각하세요 | TruLens |
| The score is <score> because <reason>. | 점수가 <score>인 이유는 <reason>입니다. | DeepEval 이유 생성 |
