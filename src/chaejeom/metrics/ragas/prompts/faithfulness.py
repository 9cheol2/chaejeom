# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/metrics/collections/faithfulness/util.py
# Changes:
#   - Instructions and field descriptions translated to Korean.
#   - New Korean few-shot examples, matching upstream's count and verdict mix:
#     one statement-generation example with 4 statements, and one verdict
#     example with 4 statements of which one has verdict 1.

from pydantic import BaseModel, Field

from chaejeom.metrics.ragas.prompts.base import RagasPrompt


class StatementGeneratorInput(BaseModel):
    question: str = Field(..., description="답변 대상 질문")
    answer: str = Field(..., description="진술로 나눌 답변 텍스트")


class StatementGeneratorOutput(BaseModel):
    statements: list[str] = Field(..., description="답변에서 만든 진술 목록")


class StatementGeneratorPrompt(RagasPrompt[StatementGeneratorInput, StatementGeneratorOutput]):
    input_model = StatementGeneratorInput
    output_model = StatementGeneratorOutput

    instruction = """질문(question)과 답변(answer)이 주어지면, 답변의 각 문장이 얼마나 복잡한지 분석하세요. 각 문장을 완전히 이해할 수 있는 하나 이상의 진술로 나누세요. 어떤 진술에도 대명사를 쓰지 않도록 하세요."""

    examples = [
        (
            StatementGeneratorInput(
                question="세종대왕은 누구이며 무엇으로 가장 잘 알려져 있나요?",
                answer="그는 조선의 제4대 왕으로, 역사상 가장 위대한 군주 중 한 명으로 널리 평가받습니다. 그는 훈민정음을 창제한 것으로 가장 잘 알려져 있으며, 측우기 같은 과학 기구의 발명을 지원하는 데에도 중요한 기여를 했습니다.",
            ),
            StatementGeneratorOutput(
                statements=[
                    "세종대왕은 조선의 제4대 왕이다.",
                    "세종대왕은 역사상 가장 위대한 군주 중 한 명으로 평가받는다.",
                    "세종대왕은 훈민정음을 창제한 것으로 가장 잘 알려져 있다.",
                    "세종대왕은 측우기 같은 과학 기구의 발명을 지원하는 데 중요한 기여를 했다.",
                ]
            ),
        ),
    ]


class StatementFaithfulnessAnswer(BaseModel):
    statement: str = Field(..., description="원래 진술, 한 글자도 바꾸지 않고 그대로")
    reason: str = Field(..., description="판정 이유")
    verdict: int = Field(..., description="충실성 판정(0/1)")


class NLIStatementInput(BaseModel):
    context: str = Field(..., description="진술을 판정할 기준이 되는 문맥")
    statements: list[str] = Field(..., description="충실성을 판정할 진술 목록")


class NLIStatementOutput(BaseModel):
    statements: list[StatementFaithfulnessAnswer] = Field(..., description="판정이 붙은 진술 목록")


class NLIStatementPrompt(RagasPrompt[NLIStatementInput, NLIStatementOutput]):
    input_model = NLIStatementInput
    output_model = NLIStatementOutput

    instruction = """당신의 임무는 주어진 문맥(context)을 바탕으로 여러 진술의 충실성을 판정하는 것입니다. 각 진술에 대해, 문맥에서 직접 추론할 수 있으면 판정(verdict)을 1로, 문맥에서 직접 추론할 수 없으면 0으로 반드시 반환하세요."""

    examples = [
        (
            NLIStatementInput(
                context="민수는 한국대학교 학생이다. 그는 컴퓨터공학을 전공하고 있다. 그는 이번 학기에 자료구조, 알고리즘, 데이터베이스 관리를 포함한 여러 과목을 수강하고 있다. 민수는 성실한 학생으로 공부와 과제에 많은 시간을 쓴다. 그는 프로젝트를 하느라 도서관에 늦게까지 남아 있는 경우가 많다.",
                statements=[
                    "민수는 생물학을 전공한다.",
                    "민수는 인공지능 과목을 수강하고 있다.",
                    "민수는 열심히 공부하는 학생이다.",
                    "민수는 아르바이트를 한다.",
                ],
            ),
            NLIStatementOutput(
                statements=[
                    StatementFaithfulnessAnswer(
                        statement="민수는 생물학을 전공한다.",
                        reason="민수의 전공은 생물학이 아니라 컴퓨터공학이라고 명시되어 있습니다.",
                        verdict=0,
                    ),
                    StatementFaithfulnessAnswer(
                        statement="민수는 인공지능 과목을 수강하고 있다.",
                        reason="문맥은 자료구조, 알고리즘, 데이터베이스 관리 과목을 언급하지만 인공지능은 언급하지 않습니다.",
                        verdict=0,
                    ),
                    StatementFaithfulnessAnswer(
                        statement="민수는 열심히 공부하는 학생이다.",
                        reason="문맥에 따르면 민수는 성실한 학생이며 공부와 과제에 많은 시간을 씁니다.",
                        verdict=1,
                    ),
                    StatementFaithfulnessAnswer(
                        statement="민수는 아르바이트를 한다.",
                        reason="문맥에는 민수가 아르바이트를 한다는 정보가 없습니다.",
                        verdict=0,
                    ),
                ]
            ),
        ),
    ]
