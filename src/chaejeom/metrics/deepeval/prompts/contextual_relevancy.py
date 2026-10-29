# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/contextual_relevancy/templates/{generate_verdicts,generate_reason}.txt
#   deepeval/metrics/contextual_relevancy/contextual_relevancy.py (_contextual_relevancy_verdict_kwargs, text-only)
#
# Changes from upstream:
# - Translated to Korean. The few-shot example is rewritten in Korean with upstream's
#   shape: two relevant sentences and one irrelevant one.
# - Only the text-only branch of the Jinja templates is ported, as f-strings.
# - The verdict prompt adds one line on reason style (`REASON_STYLE`); the verdict
#   criteria are unchanged.

from chaejeom.metrics.style import REASON_STYLE

NO_STATEMENTS_REASON = "주어진 문맥에서 진술을 찾지 못했습니다."


def generate_verdicts(input: str, context: str) -> str:
    """Build the prompt that extracts statements from one context and judges their relevance."""
    return f"""입력과 문맥을 바탕으로, 문맥에서 찾은 각 진술이 주어진 입력과 관련 있는지 나타내는 JSON 객체를 생성하세요. JSON 은 'verdicts' 목록이며, 필수 필드 2개 'verdict' 와 'statement', 선택 필드 1개 'reason' 을 가집니다.
판정과 필요하면 이유를 정하기 전에, 먼저 문맥에서 진술을 추출하세요. 진술은 문맥에 담긴 상위 수준의 정보입니다.
'verdict' 키는 반드시 'yes' 또는 'no' 중 하나여야 하며, 진술이 입력과 관련 있는지를 나타냅니다.
'reason' 은 판정이 no 일 때만 제공하세요. 이유를 뒷받침하기 위해 진술에서 관련 없는 부분을 반드시 인용하세요. {REASON_STYLE}
주어진 문맥에 실제 내용이나 진술이 없다면: "verdict" 로 "no" 를 주고,
"statement" 에는 문맥을 넣고, "reason" 에는 "{NO_STATEMENTS_REASON}" 를 넣으세요.
**
중요: JSON 형식으로만 반환하세요.
예시 문맥: "세종대왕은 훈민정음을 창제했다. 그는 1443년에 훈민정음을 완성했다. 궁궐에는 고양이가 있었다."
예시 입력: "세종대왕의 업적에는 어떤 것이 있나요?"

예시:
{{
  "verdicts": [
    {{
      "statement": "세종대왕은 1443년에 훈민정음을 창제했다",
      "verdict": "yes"
    }},
    {{
      "statement": "궁궐에는 고양이가 있었다.",
      "reason": "검색 문맥에 '궁궐에는 고양이가 있었다' 는 정보가 있지만 세종대왕의 업적과는 아무 관련이 없습니다.",
      "verdict": "no"
    }}
  ]
}}
**

입력:
{input}

문맥:
{context}

JSON:"""


def generate_reason(
    input: str,
    irrelevant_statements: list[str | None],
    relevant_statements: list[str],
    score: str,
) -> str:
    """Build the prompt that explains the contextual relevancy score."""
    return f"""주어진 입력, 검색 문맥이 입력과 관련 없는 이유, 검색 문맥 중 실제로 관련 있는 진술, 그리고 문맥 관련성 점수(1에 가까울수록 좋음)를 바탕으로 점수의 이유를 간결하게 생성하세요.
이유에서는 관련 없는 이유와 관련 있는 진술에 담긴 내용을 인용해 주장을 뒷받침하세요.

**
중요: 'reason' 키에 이유를 담은 JSON 형식으로만 반환하세요.
예시 JSON:
{{
  "reason": "점수가 <contextual_relevancy_score>인 이유는 <your_reason>입니다."
}}

점수가 1이면 짧게, 밝고 격려하는 어조로 긍정적인 말을 하세요(다만 지나치면 거슬리니 과하게 하지는 마세요).
**


문맥 관련성 점수:
{score}

입력:
{input}

검색 문맥이 입력과 관련 없는 이유:
{irrelevant_statements}

검색 문맥 중 입력과 관련 있는 진술:
{relevant_statements}

JSON:"""
