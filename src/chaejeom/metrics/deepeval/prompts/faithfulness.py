# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/faithfulness/templates/{generate_truths,generate_claims,generate_verdicts,generate_reason}.txt
#   deepeval/templates/metrics/fragments/faithfulness_verdicts_{format_instruction,guidelines_text_only}.txt
#   deepeval/metrics/faithfulness/faithfulness.py (_faithfulness_truths_limit_phrase)
#
# Changes from upstream:
# - Translated to Korean. The few-shot example is rewritten in Korean and, like
#   upstream's, contains a deliberately wrong year to illustrate the instruction that
#   factual correctness does not matter.
# - Only the text-only branch of the Jinja templates is ported, as f-strings.
# - The verdict prompt adds one line on reason style (`REASON_STYLE`); the verdict
#   criteria are unchanged.

from chaejeom.metrics.style import REASON_STYLE

_EXAMPLE_TEXT = (
    '"흔히 한글 창제로 기억되는 세종대왕은 많은 사람이 생각하는 것과 달리 측우기를 직접 발명하지는 않았다. '
    "대신 그는 1500년에 장영실을 등용해 측우기 제작을 지원했고, 측우기는 세계 최초의 강우량 측정 기구로 평가받는다.\""
)

_EXAMPLE_JSON_ITEMS = """    "세종대왕은 1500년에 장영실을 등용해 측우기 제작을 지원했다.",
    "측우기는 세계 최초의 강우량 측정 기구로 평가받는다\""""


def truths_limit_phrase(extraction_limit: int | None) -> str:
    """Return the Korean phrase describing how many truths to extract."""
    if extraction_limit is None:
        return "사실에 기반하고 논란의 여지가 없는 사실"
    if extraction_limit == 1:
        return "가장 중요한, 사실에 기반하고 논란의 여지가 없는 사실 하나"
    return f"문서마다 가장 중요한, 사실에 기반하고 논란의 여지가 없는 사실 {extraction_limit}개"


def generate_truths(retrieval_context: str, extraction_limit: int | None) -> str:
    """Build the prompt that extracts truths from the retrieval context."""
    return f"""주어진 텍스트를 바탕으로, 제공된 텍스트에서 추론할 수 있는 {truths_limit_phrase(extraction_limit)}의 포괄적인 목록을 생성하세요.
이 사실들은 반드시 앞뒤가 맞아야 합니다. 맥락에서 떼어 내서는 절대 안 됩니다.

예시:
예시 텍스트:
{_EXAMPLE_TEXT}

예시 JSON:
{{
  "truths": [
{_EXAMPLE_JSON_ITEMS}
  ]
}}
===== 예시 끝 =====
**
중요: "truths" 키에 문자열 목록이 담긴 JSON 형식으로만 반환하세요. 다른 말이나 설명은 필요 없습니다.
사실에 기반한 사실만 포함하세요. 그러나 그것이 사실로서 맞는지는 전혀 상관없습니다.
**

텍스트:
{retrieval_context}

JSON:"""


def generate_claims(actual_output: str) -> str:
    """Build the prompt that extracts claims from the answer."""
    return f"""주어진 텍스트를 바탕으로, 제공된 실제 AI 출력에서 추론할 수 있는 사실에 기반하고 논란의 여지가 없는 사실의 포괄적인 목록을 추출하세요.
이 사실들은 반드시 앞뒤가 맞아야 하며, 맥락에서 떼어 내서는 절대 안 됩니다.

예시:
예시 텍스트:
{_EXAMPLE_TEXT}

예시 JSON:
{{
  "claims": [
{_EXAMPLE_JSON_ITEMS}
  ]
}}
===== 예시 끝 =====

**
중요: "claims" 키에 문자열 목록이 담긴 JSON 형식으로만 반환하세요. 다른 말이나 설명은 필요 없습니다.
사실에 기반한 주장만 포함하세요. 그러나 그것이 사실로서 맞는지는 전혀 상관없습니다. 추출한 주장에는 원래 제시된 맥락이 모두 담겨야 하며, 일부 사실만 골라내서는 절대 안 됩니다.
사전 지식은 절대 넣지 말고, 주장을 추출할 때 텍스트를 있는 그대로 받아들이세요.
이 주장들을 출력하는 것이 AI 라는 점을 알고 있어야 합니다.
**

AI 출력:
{actual_output}

JSON:"""


def generate_verdicts(claims: list[str], retrieval_context: str) -> str:
    """Build the prompt that checks each claim against the truths."""
    return f"""문자열 목록인 주어진 주장들을 바탕으로, 주장 하나하나가 검색 문맥의 사실 정보와 모순되는지 나타내는 JSON 객체 목록을 생성하세요. JSON 에는 'verdict' 와 'reason' 두 필드가 있습니다.
'verdict' 키는 반드시 'yes', 'no', 'borderline' 중 하나여야 하며, 주어진 주장이 문맥과 일치하는지를 나타냅니다.
'reason' 은 답이 'no' 또는 'borderline' 일 때만 제공하세요.
주어진 주장은 실제 출력에서 뽑은 것입니다. 이유에는 검색 문맥의 사실 정보를 사용해 바로잡은 내용을 담도록 하세요.
{REASON_STYLE}


출력 JSON 형식:
{{
"verdicts": [
{{
"verdict": "yes"
}},
{{
"reason": <모순에 대한 설명>,
"verdict": "no"
}},
{{
"reason": <불확실함에 대한 설명>,
"verdict": "borderline"
}}
]
}}


**
중요: 'verdicts' 키에 JSON 객체 목록이 담긴 JSON 형식으로만 반환하세요.

주장 하나마다 판정을 하나씩 생성하세요. 'verdicts' 의 길이는 반드시 주장 개수와 같아야 합니다.
'yes' 판정에는 'reason' 이 필요 없습니다.
검색 문맥이 주장과 직접 모순될 때만 'no' 를 쓰세요. 사전 지식은 절대 쓰지 마세요.
문맥이 뒷받침하지 않는 주장, 또는 사실과 다르지만 모순되지는 않는 주장에는 'borderline' 을 쓰세요. 당신의 지식을 전제하지 마세요.
주장에 쓰인 모호하거나 추측하는 표현(예: '~했을 수도 있다', '가능성')은 모순으로 보지 않습니다.

**

검색 문맥:
{retrieval_context}

주장:
{claims}

JSON:"""


def generate_reason(contradictions: list[str | None], score: str) -> str:
    """Build the prompt that explains the faithfulness score."""
    return f"""아래는 모순 목록입니다. '실제 출력' 이 '검색 문맥' 에 제시된 정보와 왜 맞지 않는지 설명하는 문자열 목록입니다. 모순은 '검색 문맥' 이 아니라 '실제 출력' 에서 일어납니다.
충실성 점수는 `실제 출력` 이 검색 문맥에 얼마나 충실한지를 나타내는 0-1 점수입니다(높을수록 좋음). 이 점수를 근거로, 점수를 뒷받침할 수 있도록 모순을 간결하게 요약하세요.

출력 JSON 형식:
{{
  "reason": "점수가 <faithfulness_score>인 이유는 <your_reason>입니다."
}}

**
중요: 'reason' 키에 이유를 담은 JSON 형식으로만 반환하세요.

모순이 없다면, 밝고 격려하는 어조로 긍정적인 말을 하세요(다만 지나치면 거슬리니 과하게 하지는 마세요).
이유에는 반드시 `모순` 의 정보를 사용하세요.
모순을 보고 실제 출력이 무엇인지 아는 것처럼 확신을 갖고 이유를 쓰세요.
**

충실성 점수:
{score}

모순:
{contradictions}

JSON:"""
