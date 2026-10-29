# Adapted from trulens 2.16.0 (MIT), commit 1f65a310cd5bdaef3ea7be76e98022f574cea39c
#   src/feedback/trulens/feedback/templates/rag.py (Groundedness, Trivial, ContextRelevance, PromptResponseRelevance)
#   src/feedback/trulens/feedback/templates/base.py (LIKERT_0_3_PROMPT, COT_REASONS_TEMPLATE)
#
# Changes from upstream:
# - Prompts translated to Korean. Only the 0-3 scale and default criteria are used, so
#   templates such as criteria_template are stored as final, pre-filled strings.
# - Parsed output labels (Criteria:, Supporting Evidence:, Score:), JSON keys, and
#   NOTHING FOUND / ABSTENTION stay in English.
# - CoT user prompts append the format block directly instead of string-replacing
#   "RELEVANCE:", which upstream would also replace inside the query or context.
# - The CoT format block adds one line on reason style (`REASON_STYLE`); the criteria
#   are unchanged. Groundedness gets no style line because its supporting_evidence
#   quotes source sentences verbatim.

from chaejeom.metrics.style import REASON_STYLE

LIKERT_0_3_PROMPT = "0에서 3 사이의 숫자 (0은 기준에 따른 가장 낮은 점수, 3은 가능한 가장 높은 점수)"

COT_REASONS_TEMPLATE = f"""
다음 양식에 따라 평가하세요:

Criteria: <이번 평가의 기준을 적으세요. 평가에 쓰는 기준을 다시 서술하고, 기준에 추가 지시가 있으면 반드시 여기에 다시 적으세요.>
Supporting Evidence: <나열된 기준에 근거해 점수를 매긴 이유를 단계별로 적으세요. 진행 중인 평가와 연결해서 설명하세요.>
Score: <주어진 기준에 따른 점수>

위 양식 전체를 사용해 답하세요. {REASON_STYLE}
"""


class Groundedness:
    """Groundedness judge prompts and the LLM sentence-splitter prompt."""

    criteria = """- 근거 자료가 직접 뒷받침하는 진술은 근거가 있는 것으로 보고 높은 점수를 주어야 합니다.
- 근거 자료가 직접 뒷받침하지 않는 진술은 근거가 없는 것으로 보고 낮은 점수를 주어야 합니다.
- 의심을 나타내는 진술, 즉 불확실함을 인정하거나 답을 모른다고 하는 진술은 답변 유보로 보며, 정보 겹침이 가장 큰 것으로 계산해 최고 점수인 3을 주어야 합니다.
- 명시적인 뒷받침이 없다는 이유만으로 사실일 수 있는 주장을 불리하게 평가하지 않도록, 간접적이거나 암묵적인 증거, 또는 진술의 맥락도 고려하세요.
- 거짓 양성을 경계하세요. 분명한 뒷받침 증거가 있을 때만 높은 점수를 주어야 합니다.
- 간접적인 증거를 직접적인 뒷받침으로 착각하지 않도록 특히 주의하세요."""

    system_prompt = f"""당신은 정보 겹침 분류기입니다. 근거 자료와 진술 사이의 정보 겹침(함의 또는 근거성)을 제공합니다.
{LIKERT_0_3_PROMPT}로만 답하세요.
다음 기준에 따라 진술의 근거성을 채점하세요:
{criteria}

부연 설명은 절대 하지 마세요."""

    user_prompt = """근거 자료: {premise}
진술: {hypothesis}
정확히 다음 키를 가진 한 줄짜리 JSON 객체로만 답하세요:
  "criteria"             – 진술을 그대로 옮겨 적은 것
  "supporting_evidence"  – 진술을 뒷받침하는 근거 자료의 문장, 또는 문자열 NOTHING FOUND 나 ABSTENTION
  "score"                – 정수 0, 1, 2, 3 중 하나
예시 (형식만 참고하고 값은 반드시 바꾸세요):
{{"criteria": "...", "supporting_evidence": "...", "score": 2}}
JSON 만 반환하고 다른 것은 쓰지 마세요 (마크다운이나 추가 텍스트 금지)."""

    # Sent unformatted as the system prompt, with the statement as the user message; upstream
    # also leaves {statement} unfilled.
    sentences_splitter_prompt = """다음 진술을 개별 문장으로 나누세요:
진술: {statement}
각 문장을 새 줄에 하나씩 반환하세요."""


class Trivial:
    """Prompts that drop trivial statements before groundedness judging."""

    system_prompt = (
        "다음 진술 목록을 살펴보세요. 문체적이거나, 의례적인 인사말을 담고 있거나, "
        "주요 내용과 관련된 실질적인 정보가 없는 문장을 찾아서 제거하세요. "
        "남은 진술의 목록만 파이썬 문자열 리스트 형식으로 답하세요."
    )

    user_prompt = """전체 진술: {statements}
중요한 진술: """


class ContextRelevance:
    """Context relevance (CoT) judge prompts."""

    default_cot_prompt = """당신은 전문 검색 결과 평가자입니다. 당신에게 사용자 질의와 검색 결과가 주어집니다.
당신의 임무는 사용자 질의와의 관련성을 기준으로 검색 결과를 평가하는 것입니다. 검색 결과를 0에서 3까지의 척도로 평가하세요. 각 점수의 뜻은 다음과 같습니다:
0: 검색 결과가 사용자 질의와 전혀 관련이 없습니다.
1: 검색 결과가 사용자 질의와 관련성이 낮습니다. 사용자 질의와 아주 조금 관련된 정보가 있을 수 있지만 질의에 답하기에는 부족합니다. 검색 결과에 사용자 질의에 나오는 일부 개체에 대한 언급이나 매우 제한된 정보가 있습니다. 질의가 어떤 주제에 대한 진술이라면, 검색 결과는 그 주제와 간접적으로 관련되어 있어야 합니다.
2: 검색 결과가 사용자 질의와 중간 정도로 관련됩니다. 사용자 질의가 질문이라면, 검색 결과에 사용자 질의와 관련된 정보가 일부 있을 수 있지만 질의에 답하기에는 부족합니다. 사용자 질의가 검색어나 검색 문장이라면, 검색 결과가 사용자 질의에 나오는 개체 대부분(전부는 아님)을 중심으로 다루거나, 모든 개체가 결과에 나오지만 그것을 중심으로 다루지는 않아 중간 수준의 관련성을 가집니다. 질의가 어떤 주제에 대한 진술이라면, 검색 결과는 그 주제와 관련되어 있어야 합니다.
3: 검색 결과가 사용자 질의와 관련성이 높습니다. 사용자 질의가 질문이라면, 검색 결과에 사용자 질의에 답할 수 있는 정보가 있습니다. 그렇지 않고 검색 질의가 검색어나 검색 문장이라면, 검색 결과가 사용자 질의에 나오는 모든 개체에 대한 관련 정보를 제공하고 질의에 언급된 개체를 중심으로 다룹니다. 질의가 어떤 주제에 대한 진술이라면, 검색 결과는 그 주제를 직접 다루거나 같은 주제에 관한 것이어야 합니다.
사용자 질의와 검색 결과에 대해 단계별로 생각한 뒤 검색 결과를 평가하세요. 정확성을 위해 비판적이고 엄격하게 평가하세요.
사용자 질의와 검색 결과에 대해 단계별로 생각하고 검색 결과를 평가하세요. 평가의 근거를 제시하세요."""

    user_prompt = """사용자 질의: {question}
검색 결과: {context}
""" + COT_REASONS_TEMPLATE


class PromptResponseRelevance:
    """Answer relevance (CoT) judge prompts."""

    criteria = """- 최고 점수 3을 받으려면 응답이 프롬프트 전체와 관련 있어야 합니다.
- 응답이 프롬프트의 더 많은 부분에 관련 있는 맥락을 제공할수록 관련성 점수는 높아져야 합니다.
- 프롬프트의 어느 부분과도 관련 없는 응답은 최저 점수 0을 받아야 합니다.
- 관련 있으면서 프롬프트 전체에 완전히 답하는 응답은 3점을 받아야 합니다.
- 확신에 차 있지만 거짓인 응답은 0점을 받아야 합니다.
- 겉보기에만 관련 있는 응답은 0점을 받아야 합니다.
- 긴 응답과 짧은 응답은 똑같이 좋은 점수를 받을 수 있어야 합니다.
- '모르겠습니다' 같은 답이나 모델의 거절처럼 의도적으로 질문에 답하지 않는 답변도 가장 관련 없는 것으로 보고 0점을 주어야 합니다."""

    system_prompt = f"""당신은 관련성 채점자입니다. 응답이 프롬프트와 얼마나 관련 있는지 평가하세요.
관련성 평가 기준:
{criteria}

정확히 다음 키를 가진 한 줄짜리 JSON 객체만 출력하세요:
  "criteria"             – 채점 기준표를 참고해 판단 근거를 밝히는 간결한 한 문장. 기준에 추가 지시가 있으면 여기에 다시 적으세요.
  "supporting_evidence"  – 응답의 정확한 표현이나 증거를 들어 그렇게 채점한 이유를 설명
  "score"                – {LIKERT_0_3_PROMPT}"""

    user_prompt = """프롬프트: {prompt}
응답: {response}
""" + COT_REASONS_TEMPLATE + """이제 JSON 객체를 생성하세요."""
