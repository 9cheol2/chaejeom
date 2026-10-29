"""Prompts for organizing domain descriptions and revising judge prompt templates."""

import json

ITEM_KEYS = ("service", "groundedness", "context_relevance", "answer_relevance")

ORGANIZE = """당신은 RAG(검색 증강 생성) 시스템의 평가 설정을 돕는 도우미입니다.
채점 도구는 근거성, 문맥 관련성, 답변 관련성 세 지표로 질문, 검색된 문맥, 답변을 평가합니다.
사용자가 설명한 도메인 정보를 아래 네 항목에 나눠 다듬으세요. 이 정보는 이 도메인에서 각 지표가 무엇을 같은 것으로 보고
무엇을 엄격하게 볼지 정합니다.

[네 항목]
- service (서비스 개요): 어떤 지식을 다루는 서비스이고, 누가 무엇을 묻는가.
- groundedness (근거성 기준): 답변의 진술이 문맥으로 뒷받침되는지 볼 때 이 도메인에서 따로 볼 점.
  예: 정확해야 하는 정보의 종류와 그 정보와 함께 맞아야 하는 조건.
- context_relevance (문맥 관련성 기준): 검색된 문맥 조각이 질문과 관련 있는지 볼 때 이 도메인에서 따로 볼 점.
  예: 어떤 대상끼리 같은 대상으로 보고, 어떤 대상끼리 다른 대상으로 볼지.
- answer_relevance (답변 관련성 기준): 답변이 질문에 답하는지 볼 때 이 도메인에서 따로 볼 점.
  예: 어떤 대상끼리 같은 대상으로 볼지, 어떻게 답해야 직접 답한 것으로 볼지.

[규칙]
1. 사용자가 말한 내용만, 말한 수준 그대로 옮깁니다. 말하지 않은 내용을 지어내거나 보태지 말고, 정보가 없는 항목은 빈 문자열로 둡니다.
   사용자가 말한 기준과 조건은 줄이거나 빠뜨리지 말고 모두 옮깁니다. 한 기준이 여러 지표에 해당하면 해당하는 항목마다 적습니다.
   문장은 판정 모델이 읽기 쉬운 짧은 규칙으로 다듬고, 사용자가 든 예는 함께 옮깁니다.
2. 항목에는 정보의 종류와 판정 기준만 씁니다. 구체적인 값이나 사실(예: "수수료는 3%", "휴가는 5일")은 평가의 정답이 될 수 있으므로
   쓰지 말고 "수수료율", "휴가 일수"처럼 종류로 바꿉니다. 실제 값이 들어 있던 원문만 removed_facts 에 적습니다.
3. out_of_scope 에는 말투, 길이, 형식처럼 세 지표가 재지 않는 요구만 원문으로 적고, 항목에는 넣지 않습니다.
4. name 에는 도메인을 짧게 부르는 이름을 씁니다 (예: "은행 예금 상담").
5. 반드시 JSON 만 출력하세요.

[출력 형식]
{output_format}

[예시]
사용자 설명: 은행 예금 상담 챗봇이에요. 정기예금 금리가 연 3.5%인데 이런 금리를 틀리면 안 돼요. 예금을 물으면 정기예금이나 적금으로 답해도 되지만, 정기예금을 물었는데 적금으로 답하면 안 돼요. 답변은 친절하게 해 주세요.
출력:
{example}

이제 아래 설명을 정리하세요.

[사용자 설명]
{description}
"""

ORGANIZE_RETRY = """
[다시 정리하기]
이전 결과의 항목에 정답이 될 수 있는 값이 남아 있었습니다: {values}
이 값들을 정보의 종류로 바꿔 다시 정리하세요."""

OUTPUT_FORMAT = json.dumps(
    {"name": "...", "items": {key: "..." for key in ITEM_KEYS}, "removed_facts": [], "out_of_scope": []},
    ensure_ascii=False,
)

EXAMPLE = json.dumps(
    {
        "name": "은행 예금 상담",
        "items": {
            "service": "고객이 은행 예금 상품에 대해 묻는 상담 챗봇",
            "groundedness": "예금 금리는 문맥과 정확히 같아야 맞는 것으로 본다.",
            "context_relevance": "예금을 물으면 정기예금이나 적금을 다룬 조각도 같은 대상이다. 정기예금을 물었을 때 적금을 다룬 조각은 다른 대상이다.",
            "answer_relevance": "예금을 물었는데 정기예금이나 적금으로 답하면 같은 대상이다. 정기예금을 물었는데 적금으로 답하면 다른 대상이다.",
        },
        "removed_facts": ["정기예금 금리가 연 3.5%"],
        "out_of_scope": ["답변은 친절하게 해 주세요."],
    },
    ensure_ascii=False,
)


def organize(description: str) -> str:
    return ORGANIZE.format(output_format=OUTPUT_FORMAT, example=EXAMPLE, description=description)


REVISE = """당신은 RAG 평가 프롬프트를 고치는 편집자입니다. 아래 [현재 프롬프트]는 채점 도구의 "{metric}" 지표 판정 프롬프트 틀입니다.
사용자의 [요청]을 요청한 수준 그대로 반영해 프롬프트를 고치세요. 짧은 요청이면 필요한 곳만, 자세한 요청이면 그만큼 고칩니다.

[지켜야 할 것]
- 이 지표가 재는 것은 바꾸지 않습니다. "[평가 지표]"로 시작하는 줄은 글자 하나 바꾸지 않습니다.
- 중괄호 한 겹으로 된 자리 표시(예: {{query}}, {{contexts}})는 모두 그대로 한 번씩 남기고, 새 자리 표시를 만들지 않습니다.
- "[출력 형식]" 부분은 글자 하나 바꾸지 않습니다. 중괄호 두 겹({{{{, }}}})도 그대로 둡니다.
- 새로 쓰는 문장에 중괄호 문자가 필요하면 두 겹으로 씁니다.
- 판정 값 이름(supported, contradicted, true, false 등)과 JSON 키 이름은 바꾸지 않습니다.
- 요청과 관계없는 부분은 그대로 둡니다.

반드시 JSON 만 출력하세요.
{{"template": "고친 프롬프트 틀 전체", "summary": "무엇을 어떻게 바꿨는지 한두 문장"}}

[요청]
{request}

[현재 프롬프트]
{template}
"""

REVISE_RETRY = """

[다시 고치기]
이전 결과가 지켜야 할 것을 어겼습니다: {problems}
[현재 프롬프트]에서 다시 시작해 요청을 반영하되, 위 문제가 없게 고치세요."""


def revise(metric: str, template: str, request: str) -> str:
    return REVISE.format(metric=metric, template=template, request=request)
