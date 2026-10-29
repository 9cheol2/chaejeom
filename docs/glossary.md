# Glossary

**English | [한국어](glossary.ko.md)**

The rules for translating the original prompts of the nine upstream metrics into Korean.
Sources: Ragas v0.4.3, DeepEval 4.3.1 and TruLens 2.16.0 (commits in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).

## 1. Principles

| Principle | Rule |
|---|---|
| One to one | Words that differ in the original stay different in Korean. For example, answer is 답변 and response is 응답 |
| Keep each framework's terms | When frameworks name the same thing differently, keep the difference. For example, RAGAS question, DeepEval input, TruLens USER QUERY |
| Meaning first | When a literal translation reads badly, translate the meaning, without widening or narrowing the judging criteria |
| Keep the person | A second-person original becomes "당신은 ...입니다" and a first-person one "저는 ...하겠습니다" (the second RAGAS ContextRelevance judge prompt is first person) |
| Instruction style | Instructions use the "하세요" form throughout |
| Output style | Reasons, explanations and the reasons in few-shot examples use the polite "습니다" form. Judging units such as statements, claims and truths keep the plain "이다" form of the original, because the next step copies them word for word. Example contexts use the "한다" form, like real documents. Prompts whose original has no example reason get one line that sets the style (`src/chaejeom/metrics/style.py`) |
| Emphasis | Capitalized emphasis in the original (MUST, STRICTLY, ONLY, NEVER) becomes a Korean intensifier such as "반드시", "오직" or "절대". `**` separators in the original stay |
| Key names | Where the text refers to a JSON key, the first mention gives both, as "Korean (English key)". For example, 판정(verdict) |
| Few-shot examples | Rewritten in Korean, keeping the original number of examples and mix of verdicts. For example, the RAGAS Faithfulness verdict example has four statements, one marked 1 and three marked 0 |

## 2. Not translated

| What | Examples | Why |
|---|---|---|
| JSON keys | `statements`, `verdict`, `reason`, `claims`, `truths`, `verdicts`, `statement`, `rating`, `question`, `noncommittal`, `criteria`, `supporting_evidence`, `score` | Parsed as structured output |
| Verdict labels | `yes`, `no`, `borderline`, `0`, `1`, `2`, `3` | The aggregation formulas use these values as they are |
| TruLens output labels | `Criteria:`, `Supporting Evidence:`, `Score:` | The response is parsed by looking for these strings. They are treated as machine markers, like JSON keys, so the upstream parser can be used unchanged. The text after each label is in Korean |
| Special values | `NOTHING FOUND`, `ABSTENTION` | Values of supporting_evidence in TruLens Groundedness |
| Template variables | `{{ claims }}`, `{premise}`, `{max_score}` and others | Filled in by code |
| Metric names | Faithfulness, ContextRelevance, ResponseRelevancy, ContextualRelevancy, AnswerRelevancy, Groundedness, Context Relevance, Answer Relevance | Proper names of the upstream metrics |

## 3. What is evaluated

| Original | Korean | Meaning | Used in |
|---|---|---|---|
| question | 질문 | The user's question | RAGAS Faithfulness, ContextRelevance |
| answer | 답변 | The RAG answer under evaluation | RAGAS Faithfulness, ResponseRelevancy |
| response | 응답 | The RAG answer under evaluation | RAGAS ResponseRelevancy input field, TruLens RESPONSE |
| input | 입력 | The user input | DeepEval AnswerRelevancy, ContextualRelevancy |
| actual output | 실제 출력 | The AI output under evaluation | DeepEval |
| AI output | AI 출력 | The AI output under evaluation | DeepEval Faithfulness |
| text | 텍스트 | The text to break down | DeepEval |
| context | 문맥 | A retrieved document | All |
| retrieval context | 검색 문맥 | A retrieved document | DeepEval |
| SOURCE | 근거 자료 | A retrieved document | TruLens Groundedness |
| STATEMENT | 진술 | An answer sentence to judge | TruLens Groundedness |
| USER QUERY | 사용자 질의 | The user's question | TruLens Context Relevance |
| SEARCH RESULT | 검색 결과 | A retrieved chunk | TruLens Context Relevance |
| PROMPT | 프롬프트 | The input given to the agent | TruLens Answer Relevance |

The capitalized TruLens labels use the same Korean label in the system prompt and the user prompt. For example,
`USER QUERY:` becomes `사용자 질의:` in both.

## 4. Judging units

| Original | Korean | Meaning | Used in |
|---|---|---|---|
| statement | 진술 | A unit split from the answer or a context | RAGAS Faithfulness, DeepEval AnswerRelevancy, ContextualRelevancy, TruLens |
| claim | 주장 | A factual unit taken from the answer | DeepEval Faithfulness |
| truth | 사실 | A factual unit taken from the contexts | DeepEval Faithfulness |
| fact | 사실 정보 | Information in the contexts | DeepEval Faithfulness |
| sentence | 문장 | A unit of sentence splitting | RAGAS, TruLens |
| contradiction | 모순 | A claim at odds with the contexts | DeepEval Faithfulness |
| irrelevant statement | 관련 없는 진술 | A statement unrelated to the question | DeepEval |

## 5. Verdicts and scales

| Original | Korean | Meaning | Used in |
|---|---|---|---|
| verdict | 판정 | The verdict for one unit | All |
| reason | 이유 | The explanation behind a verdict | All |
| score | 점수 | The final score or a unit's score | All |
| relevance score | 관련성 점수 | The RAGAS 0, 1 or 2 rating | RAGAS ContextRelevance |
| criteria | 기준 | The grading criteria | TruLens |
| supporting evidence | 뒷받침 근거 | The sentences a score is based on | TruLens |
| faithfulness | 충실성 | How faithful the answer is to the contexts | RAGAS, DeepEval prompt text |
| groundedness | 근거성 | How well the sources support the answer | TruLens, axis name |
| relevance | 관련성 | How closely something addresses the question | All, axis name |
| relevant / irrelevant | 관련 있는 / 관련 없는 | | All |
| directly inferred | 직접 추론할 수 있는 | Derivable from the contexts alone | RAGAS Faithfulness |
| contradict | 모순되다 | To be at odds with the contexts | DeepEval Faithfulness |
| agree with | 일치하다 | To match the contexts | DeepEval Faithfulness |
| partially | 부분적으로 | | RAGAS ContextRelevance |
| prior knowledge | 사전 지식 | What the model already knew | All |
| noncommittal | 회피성 | Avoiding a definite answer | RAGAS ResponseRelevancy |
| evasive | 회피하는 | | RAGAS ResponseRelevancy |
| vague | 모호한 | | RAGAS ResponseRelevancy |
| ambiguous | 애매한 | | RAGAS ResponseRelevancy, DeepEval borderline description |
| substantive | 실질적인 | Having real content | RAGAS ResponseRelevancy, TruLens Trivial |
| abstention | 답변 유보 | A response such as "I don't know" | TruLens Groundedness |
| trivial pleasantries | 의례적인 인사말 | | TruLens Trivial |
| stylistic | 문체적인 | Form without content | TruLens Trivial |
| entailment | 함의 | The source implies the statement | TruLens Groundedness |
| information overlap | 정보 겹침 | | TruLens Groundedness |
| false positive | 거짓 양성 | A high score with no support | TruLens Groundedness |
| full mark | 만점 | | TruLens Context Relevance |
| intermediate score | 중간 점수 | | TruLens Context Relevance |

### Terms added while porting the metrics

| Original | Korean | Used in |
|---|---|---|
| rating | 등급 | RAGAS ContextRelevance field description (kept apart from 관련성 점수 for relevance score) |
| Question / Context (capitalized) | 질문(Question) / 문맥(Context) | RAGAS ContextRelevance |
| generated question | 역질문 | RAGAS ResponseRelevancy |
| coherent | 앞뒤가 맞는 | DeepEval Faithfulness |
| undisputed | 논란의 여지가 없는 | DeepEval Faithfulness |
| factual | 사실에 기반한 | DeepEval Faithfulness |
| factually correct | 사실로서 맞는 | DeepEval Faithfulness |
| cherry picked | 일부만 골라낸 | DeepEval Faithfulness |
| high level information | 상위 수준의 정보 | DeepEval ContextualRelevancy |
| supporting information | 보조 정보 | DeepEval AnswerRelevancy |
| parseable JSON | 파싱 가능한 JSON | DeepEval |
| (Ambiguous) | (애매함) | DeepEval Faithfulness reason generation |
| entity | 개체 | TruLens Context Relevance |
| tangentially related | 간접적으로 관련된 | TruLens Context Relevance |
| search phrase | 검색어, 검색 문장 | TruLens Context Relevance |
| rubric | 채점 기준표 | TruLens Answer Relevance |

## 6. Judge roles

| Original | Korean | Used in |
|---|---|---|
| expert | 전문가 | RAGAS ContextRelevance |
| classifier | 분류기 | TruLens Groundedness |
| grader | 채점자 | TruLens Context Relevance, Answer Relevance |
| rater | 평가자 | TruLens Context Relevance (chain-of-thought prompt) |
| judge (units.type) | 판정 프롬프트 | The two judge prompts of RAGAS ContextRelevance |

## 7. Prompt template phrases

| Original | Korean | Used in |
|---|---|---|
| Example 1 / Input / Output | 예시 1 / 입력 / 출력 | RAGAS prompt template |
| --------EXAMPLES----------- | --------예시----------- | RAGAS prompt template |
| Now perform the same with the following input | 이제 다음 입력에 대해 같은 작업을 수행하세요 | RAGAS prompt template |
| Please return the output in a JSON format that complies with the following schema as specified in JSON Schema | 다음 JSON Schema 를 따르는 JSON 형식으로 출력하세요 | RAGAS prompt template |
| Example / Example JSON / Example Text | 예시 / 예시 JSON / 예시 텍스트 | DeepEval |
| ===== END OF EXAMPLE ====== | ===== 예시 끝 ===== | DeepEval |
| IMPORTANT: | 중요: | DeepEval |
| Expected JSON format: | 출력 JSON 형식: | DeepEval |
| JSON: | JSON: | DeepEval (kept as is) |
| Never elaborate. | 부연 설명은 절대 하지 마세요. | TruLens |
| Respond only as a number from ... | ... 사이의 숫자로만 답하세요. | TruLens |
| Think step by step | 단계별로 생각하세요 | TruLens |
| The score is <score> because <reason>. | 점수가 <score>인 이유는 <reason>입니다. | DeepEval reason generation |
