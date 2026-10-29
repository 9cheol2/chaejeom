# Adapted from deepeval 4.3.1 (Apache-2.0), commit 29dcf5f24397715a60348c1e41e7d416a3b2d6c8
#   deepeval/metrics/answer_relevancy/templates/{generate_statements,generate_verdicts,generate_reason}.txt
#
# Changes from upstream:
# - Translated to Korean. The few-shot example is rewritten in Korean with upstream's
#   shape: a five-sentence product description yielding five statements, the second of
#   which omits its subject as in upstream.
# - Only the text-only branch of the Jinja templates is ported, as f-strings.
# - The verdict prompt adds one line on reason style (`REASON_STYLE`); the verdict
#   criteria are unchanged.

from chaejeom.metrics.style import REASON_STYLE


def generate_statements(actual_output: str) -> str:
    """Build the prompt that splits the answer into statements."""
    return f"""주어진 텍스트를 나누어, 그 안에 제시된 진술의 목록을 생성하세요. 애매한 진술과 단어 하나도 진술로 볼 수 있지만, 앞뒤가 맞는 진술 밖에 있을 때만 그렇습니다.

예시:
예시 텍스트:
새 무선 이어폰은 주변 소음을 줄여 주는 노이즈 캔슬링 기능을 갖추고 있습니다. 또한 한 번 충전으로 최대 8시간 재생할 수 있는 배터리를 탑재했습니다. 생활 방수를 위해 IPX4 등급을 받았고, 전용 앱으로 음질을 조정할 수 있습니다. 게다가 모든 구매에는 1년 보증과 24시간 고객 지원이 포함됩니다.



{{
  "statements": [
    "새 무선 이어폰에는 노이즈 캔슬링 기능이 있다.",
    "한 번 충전으로 최대 8시간 재생할 수 있는 배터리를 탑재했다.",
    "생활 방수 IPX4 등급을 받았고 전용 앱으로 음질을 조정할 수 있다.",
    "모든 구매에는 1년 보증이 포함된다.",
    "24시간 고객 지원이 포함된다."
  ]
}}
===== 예시 끝 =====

**
중요: "statements" 키에 문자열 목록이 대응하는, 올바르고 파싱 가능한 JSON 형식으로만 반환하세요. 다른 말이나 설명은 필요 없습니다. 모든 문자열을 올바르게 닫으세요. 출력하기 전에 잘못된 JSON 은 고치세요.
**

텍스트:
{actual_output}

JSON:"""


def generate_verdicts(input: str, statements: list[str]) -> str:
    """Build the prompt that judges each statement's relevance to the input."""
    return f"""주어진 진술 목록에 대해, 각 진술이 입력에 답하는 데 관련이 있는지 판단하세요.
'verdict' 와 'reason' 필드를 가진 JSON 객체를 생성하세요.
'verdict' 는 'yes'(관련 있음), 'no'(관련 없음), 'borderline'(애매함 또는 보조 정보) 중 하나여야 합니다.
'reason' 은 'no' 또는 'borderline' 판정일 때만 제공하세요.
진술들은 AI 의 실제 출력에서 나온 것입니다.
{REASON_STYLE}



**
중요: 'verdicts' 키에 JSON 객체 목록이 대응하는, 올바르고 파싱 가능한 JSON 형식으로만 반환하세요. 모든 문자열을 올바르게 닫으세요. 출력하기 전에 잘못된 JSON 은 고치세요.

출력 JSON 형식:
{{
  "verdicts": [
    {{
      "verdict": "yes"
    }},
    {{
      "reason": <관련 없음에 대한 설명>,
      "verdict": "no"
    }},
    {{
      "reason": <애매함에 대한 설명>,
      "verdict": "borderline"
    }}
  ]
}}

진술 하나마다 판정을 하나씩 생성하세요. 'verdicts' 의 개수는 반드시 진술 개수와 같아야 합니다.
'verdict' 는 반드시 'yes', 'no', 'borderline' 중 하나여야 합니다:
- 'yes': 진술이 입력에 답하는 데 관련 있음
- 'no': 진술이 입력과 관련 없음
- 'borderline': 진술이 애매함 (직접 관련되지는 않지만 보조 정보가 될 수 있음)
'reason' 은 'no' 또는 'borderline' 판정일 때만 제공하세요.
**

입력:
{input}

진술:
{statements}

JSON:"""


def generate_reason(irrelevant_statements: list[str | None], input: str, score: str) -> str:
    """Build the prompt that explains the answer relevancy score."""
    return f"""답변 관련성 점수, 실제 출력에 담긴 관련 없는 진술의 이유 목록, 그리고 입력을 바탕으로 점수의 이유를 간결하게 제시하세요. 점수가 왜 더 높지 않은지, 그리고 왜 지금 점수인지도 설명하세요.
관련 없는 진술은 실제 출력 중에서 입력이 묻거나 이야기하는 내용에 답하는 것과 관련 없는 부분을 나타냅니다.
관련 없는 것이 없다면, 밝고 격려하는 어조로 긍정적인 말을 하세요(다만 지나치면 거슬리니 과하게 하지는 마세요).



**
중요: 'reason' 키에 이유를 담은 JSON 형식으로만 반환하세요. 모든 문자열을 올바르게 닫으세요. 출력하기 전에 잘못된 JSON 은 고치세요.

예시:
예시 JSON:
{{
  "reason": "점수가 <answer_relevancy_score>인 이유는 <your_reason>입니다."
}}
===== 예시 끝 =====
**


답변 관련성 점수:
{score}

실제 출력의 관련 없는 진술로 볼 때 점수가 더 높을 수 없는 이유:
{irrelevant_statements}

입력:
{input}

JSON:"""
