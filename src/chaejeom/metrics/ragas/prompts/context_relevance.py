# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/context_relevance/util.py
# Changes:
#   - Instructions and field descriptions translated to Korean. Judge 2 keeps
#     upstream's first-person voice.
#   - New Korean few-shot examples, matching upstream's count and rating mix:
#     3 per judge prompt, rated 2, 2, 0.

from pydantic import BaseModel, Field

from chaejeom.metrics.ragas.prompts.base import RagasPrompt


class ContextRelevanceInput(BaseModel):
    user_input: str = Field(..., description="사용자의 질문")
    context: str = Field(..., description="관련성을 평가할 문맥")


class ContextRelevanceOutput(BaseModel):
    rating: int = Field(..., description="관련성 등급 (0, 1, 2)")


class ContextRelevanceJudge1Prompt(RagasPrompt[ContextRelevanceInput, ContextRelevanceOutput]):
    input_model = ContextRelevanceInput
    output_model = ContextRelevanceOutput

    instruction = """당신은 질문(Question)에 답하기 위한 문맥(Context)의 관련성 점수를 평가하도록 설계된 세계 최고 수준의 전문가입니다.
당신의 임무는 문맥에 질문에 답하기 위한 적절한 정보가 있는지 판단하는 것입니다.
질문에 대한 사전 지식에 의존하지 마세요.
문맥과 질문에 쓰인 내용만 사용하세요.
아래 지시를 따르세요:
0. 문맥에 질문에 답하는 데 관련된 정보가 전혀 없으면 0이라고 답하세요.
1. 문맥에 질문에 답하는 데 관련된 정보가 부분적으로 있으면 1이라고 답하세요.
2. 문맥에 질문에 답하는 데 관련된 정보가 있으면 2라고 답하세요.
관련성 점수는 반드시 0, 1, 2 중 하나로만 답하고, 다른 것은 쓰지 마세요.
설명하지 마세요.
응답은 {"rating": X} 형식의 JSON 으로 반환하세요. X 는 0, 1, 2 중 하나입니다."""

    examples = [
        (
            ContextRelevanceInput(
                user_input="세종대왕은 언제 태어났나요?",
                context="세종대왕은 1397년 5월 15일에 태어났다.",
            ),
            ContextRelevanceOutput(rating=2),
        ),
        (
            ContextRelevanceInput(
                user_input="광합성이란 무엇인가요?",
                context="광합성은 식물이 햇빛을 에너지로 바꾸는 과정이다.",
            ),
            ContextRelevanceOutput(rating=2),
        ),
        (
            ContextRelevanceInput(
                user_input="컴퓨터는 어떻게 작동하나요?",
                context="세종대왕은 조선의 제4대 왕이다.",
            ),
            ContextRelevanceOutput(rating=0),
        ),
    ]


class ContextRelevanceJudge2Prompt(RagasPrompt[ContextRelevanceInput, ContextRelevanceOutput]):
    input_model = ContextRelevanceInput
    output_model = ContextRelevanceOutput

    instruction = """저는 주어진 문맥(Context)이 질문(Question)에 대해 얼마나 관련 있는지 관련성 점수를 평가하도록 특별히 설계된 전문가로서, 문맥이 질문에 답하는 데 필요한 정보를 어느 정도 제공하는지 판단하는 것이 제 임무입니다. 저는 사전 지식이 아니라 문맥과 질문에 주어진 정보에만 의존하겠습니다.

제가 따를 지시는 다음과 같습니다:
* 문맥에 질문에 답하는 데 관련된 정보가 전혀 없으면, 관련성 점수 0으로 답하겠습니다.
* 문맥에 질문에 답하는 데 관련된 정보가 부분적으로 있으면, 관련성 점수 1로 답하겠습니다.
* 문맥에 질문에 답하는 데 관련된 정보가 있으면, 관련성 점수 2로 답하겠습니다.
응답은 {"rating": X} 형식의 JSON 으로 반환하세요. X 는 0, 1, 2 중 하나입니다."""

    examples = [
        (
            ContextRelevanceInput(
                user_input="세종대왕은 언제 태어났나요?",
                context="세종대왕은 1397년 5월 15일에 태어났다.",
            ),
            ContextRelevanceOutput(rating=2),
        ),
        (
            ContextRelevanceInput(
                user_input="광합성이란 무엇인가요?",
                context="광합성은 식물이 햇빛을 에너지로 바꾸는 과정이다.",
            ),
            ContextRelevanceOutput(rating=2),
        ),
        (
            ContextRelevanceInput(
                user_input="컴퓨터는 어떻게 작동하나요?",
                context="오늘은 날씨가 맑다.",
            ),
            ContextRelevanceOutput(rating=0),
        ),
    ]
