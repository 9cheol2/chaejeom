# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/answer_relevancy/util.py
# Changes:
#   - Instructions and field descriptions translated to Korean.
#   - New Korean few-shot examples, matching upstream's count and verdict mix:
#     3 examples with noncommittal 0, 0, 1.

from pydantic import BaseModel, Field

from chaejeom.metrics.ragas.prompts.base import RagasPrompt


class AnswerRelevanceInput(BaseModel):
    response: str = Field(..., description="질문을 생성할 응답/답변")


class AnswerRelevanceOutput(BaseModel):
    question: str = Field(..., description="응답으로 답할 수 있는 질문")
    noncommittal: int = Field(..., description="응답이 회피하거나 모호하면 1, 실질적이면 0")


class AnswerRelevancePrompt(RagasPrompt[AnswerRelevanceInput, AnswerRelevanceOutput]):
    input_model = AnswerRelevanceInput
    output_model = AnswerRelevanceOutput

    instruction = """주어진 답변에 대한 질문을 생성하고, 답변이 회피성(noncommittal)인지 판별하세요.
답변이 회피성이면(회피하거나, 모호하거나, 애매하면) noncommittal 을 1로, 답변이 실질적이면 0으로 주세요.
회피성 답변의 예: "모르겠습니다", "잘 모르겠어요", "경우에 따라 다릅니다"."""

    examples = [
        (
            AnswerRelevanceInput(response="세종대왕은 한양에서 태어났습니다."),
            AnswerRelevanceOutput(question="세종대왕은 어디에서 태어났나요?", noncommittal=0),
        ),
        (
            AnswerRelevanceInput(response="대한민국의 수도는 서울이며, 역사와 문화로 잘 알려진 도시입니다."),
            AnswerRelevanceOutput(question="대한민국의 수도는 어디인가요?", noncommittal=0),
        ),
        (
            AnswerRelevanceInput(
                response="저는 2022년 이후의 정보를 알지 못하기 때문에 2023년에 발명된 스마트폰의 획기적인 기능에 대해서는 모르겠습니다."
            ),
            AnswerRelevanceOutput(
                question="2023년에 발명된 스마트폰의 획기적인 기능은 무엇이었나요?",
                noncommittal=1,
            ),
        ),
    ]
