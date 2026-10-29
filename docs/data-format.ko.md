# 데이터 형식

**[English](data-format.md) | 한국어**

채점은 JSONL(한 줄에 샘플 하나), 샘플 목록이 든 JSON, CSV(한 행에 샘플 하나)를 UTF-8로 읽습니다. 한국어 엑셀로
저장한 CSV(CP949)도 읽습니다.

## 필드

```jsonl
{"query": "재택근무는 일주일에 며칠까지 가능한가요?", "contexts": ["재택근무는 주 2일까지 신청할 수 있다.", "구내식당은 11시 30분에 연다."], "answer": "주 2일까지 가능합니다."}
{"id": "hr-002", "query": "...", "contexts": [{"id": "doc-12", "text": "..."}], "answer": "...", "metadata": {"retriever": "bm25"}}
```

| 필드 | 형식 | 설명 |
|---|---|---|
| `query` | 문자열 | 사용자 질문 |
| `contexts` | 문자열 목록 또는 `{id, text, rank}` 목록 | 검색된 문서, 순위 순서대로. `id`와 `rank`는 생략할 수 있고, 차례로 `c1, c2, ...`와 `1, 2, ...`가 됨 |
| `answer` | 문자열 | 평가할 답변 |
| `id` | 문자열 또는 정수 | 선택. 결과와 `chaejeom compare`에서 샘플을 찾을 때 씀. 생략하면 0부터 센 순번 |
| `metadata` | 객체 | 선택. 결과에 그대로 복사됨 |

모든 필드는 생략할 수 있습니다. 지표에 필요한 필드가 비어 있으면 그 샘플에서 그 지표만 오류를 남기고, 나머지는
계속 실행됩니다.

### 지표별 필요한 입력

| 지표 | query | contexts | answer | 임베딩 |
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

`chaejeom list`로도 같은 내용을 볼 수 있습니다.

## 다른 프레임워크의 필드 이름

RAGAS나 DeepEval용으로 만든 데이터도 그대로 쓸 수 있습니다.

| 채점 | RAGAS | DeepEval |
|---|---|---|
| `query` | `user_input` | `input` |
| `contexts` | `retrieved_contexts` | `retrieval_context` |
| `answer` | `response` | `actual_output` |

다음 두 종류의 추가 필드는 오류 대신 안내와 함께 받습니다.

| 필드 | 처리 |
|---|---|
| 정답 필드: `reference`, `reference_contexts`, `ground_truth`, `ground_truths`, `expected_output`, `expected_answer`, `context`(DeepEval의 정답 문맥), `golden_answer`, `reference_answer` | 모든 지표가 레퍼런스 프리라서 쓰지 않음 |
| 그 밖의 필드 (`user_id`, `timestamp` 등) | `metadata`로 옮겨 결과에 남김 |

## CSV

첫 행은 열 이름이고, 그다음부터 한 행에 샘플 하나입니다. 검색된 문서는 `context_1`, `context_2`, ... 열에 하나씩
넣고, 빈 칸은 건너뜁니다. JSON 목록(`["...", "..."]`)이 든 `contexts` 열(또는 `retrieved_contexts`,
`retrieval_context`)도 되며, 그 열의 다른 값은 문맥 하나로
읽으므로 `[공지] ...` 같은 문서도 문제없습니다. `metadata.<키>`(또는 결과 CSV처럼 `meta.<키>`) 열은 `metadata`로
들어갑니다.

```csv
id,query,context_1,context_2,answer,metadata.case
hr-01,재택근무는 일주일에 며칠까지 가능한가요?,재택근무는 주 2일까지 신청할 수 있다.,구내식당은 11시 30분에 연다.,주 2일까지 가능합니다.,correct
```

[examples/samples.csv](../examples/samples.csv)에는 [examples/samples.jsonl](../examples/samples.jsonl)과 같은
샘플이 들어 있습니다.

## 형식 오류

다음 경우에는 무엇이 틀렸는지와 올바른 형식을 보여 주고 불러오기를 멈춥니다.

| 문제 | 예 |
|---|---|
| 확장자가 `.jsonl`, `.json`, `.csv`가 아님 | `samples.txt` |
| 파일에 샘플이 없음 | 빈 파일, 열 이름만 있는 CSV |
| UTF-8이 아님 (CSV는 CP949도 됨) | CP949로 저장한 JSONL |
| 줄이 올바른 JSON이 아님 | 중간에 잘린 줄 |
| CSV 행의 칸이 열 이름보다 많음 | 따옴표 없이 칸 안에 쉼표가 있음 |
| `.json` 파일이 목록이 아님 | `[{"query": ...}]` 대신 `{"query": ...}` |
| 샘플이 객체가 아님 | `"그냥 텍스트"` |
| 샘플에 `query`, `contexts`, `answer`가 하나도 없음 | `id`와 `metadata`만 있음 |
| 값의 형식이 틀림 | `contexts`를 문자열 하나로 줌 |
