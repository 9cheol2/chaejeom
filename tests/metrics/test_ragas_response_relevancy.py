import json
import math

import pytest
from fakes import ScriptedLLM

from chaejeom.embeddings import EmbeddingClient
from chaejeom.metrics import get_metric
from chaejeom.schema import EvalSample

SAMPLE = EvalSample(query="재택근무는 며칠까지 되나요?", answer="재택근무는 팀장 승인을 받아 주 2일까지 할 수 있습니다.")


class FakeEmbeddings(EmbeddingClient):
    def __init__(self, vectors: dict[str, list[float]]):
        super().__init__("fake")
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[t] for t in texts]


def _response(question: str, noncommittal: int = 0) -> str:
    return json.dumps({"question": question, "noncommittal": noncommittal}, ensure_ascii=False)


def _metric(responses: list[str], vectors: dict[str, list[float]], **options):
    llm = ScriptedLLM(responses)
    embeddings = FakeEmbeddings(vectors)
    metric = get_metric("ragas.response_relevancy")(llm=llm, embeddings=embeddings, options=options)
    return metric, llm, embeddings


VECTORS = {
    SAMPLE.query: [1.0, 0.0],
    "재택근무는 며칠 가능한가요?": [1.0, 0.0],
    "재택근무 승인은 누가 하나요?": [0.6, 0.8],
    "사내 식당은 언제 여나요?": [0.0, 1.0],
}


async def test_score_is_mean_cosine_similarity():
    questions = ["재택근무는 며칠 가능한가요?", "재택근무 승인은 누가 하나요?", "사내 식당은 언제 여나요?"]
    metric, llm, embeddings = _metric([_response(q) for q in questions], VECTORS)

    result = await metric.ameasure(SAMPLE)

    assert result.score == pytest.approx((1.0 + 0.6 + 0.0) / 3)
    assert result.raw_score == pytest.approx(result.score)
    assert result.axis == "answer_relevance"
    assert [u.text for u in result.units] == questions
    assert [u.score for u in result.units] == pytest.approx([1.0, 0.6, 0.0])
    assert all(u.type == "generated_question" and u.verdict == 0 for u in result.units)
    assert result.cost.llm_calls == 3
    assert embeddings.calls == [[SAMPLE.query], questions]


async def test_cosine_is_normalized_by_vector_length():
    vectors = {SAMPLE.query: [2.0, 0.0], "질문": [3.0, 4.0]}
    metric, _, _ = _metric([_response("질문")], vectors, strictness=1)

    result = await metric.ameasure(SAMPLE)

    assert result.score == pytest.approx(0.6)


async def test_zero_only_when_all_noncommittal():
    some = [_response("재택근무는 며칠 가능한가요?", 1), _response("재택근무 승인은 누가 하나요?", 0)]
    metric, _, _ = _metric(some, VECTORS, strictness=2)
    assert (await metric.ameasure(SAMPLE)).score == pytest.approx(0.8)

    every = [_response("재택근무는 며칠 가능한가요?", 1), _response("재택근무 승인은 누가 하나요?", 1)]
    metric, _, _ = _metric(every, VECTORS, strictness=2)
    result = await metric.ameasure(SAMPLE)
    assert result.score == 0.0
    assert result.raw_score == pytest.approx(0.8)
    assert "회피성" in result.reason


async def test_empty_questions_are_skipped():
    metric, _, embeddings = _metric([_response(""), _response("재택근무는 며칠 가능한가요?")], VECTORS, strictness=2)

    result = await metric.ameasure(SAMPLE)

    assert len(result.units) == 1
    assert result.score == pytest.approx(1.0)
    assert embeddings.calls[1] == ["재택근무는 며칠 가능한가요?"]


async def test_no_questions_gives_zero_without_embedding():
    metric, _, embeddings = _metric([_response("")] * 3, VECTORS)

    result = await metric.ameasure(SAMPLE)

    assert result.score == 0.0
    assert embeddings.calls == []


async def test_zero_vector_gives_no_score():
    vectors = {SAMPLE.query: [0.0, 0.0], "질문": [1.0, 0.0]}
    metric, _, _ = _metric([_response("질문")], vectors, strictness=1)

    with pytest.warns(RuntimeWarning):
        result = await metric.ameasure(SAMPLE)

    assert result.score is None
    assert math.isnan(result.units[0].score)


def test_requires_embeddings_and_default_strictness():
    with pytest.raises(ValueError, match="임베딩"):
        get_metric("ragas.response_relevancy")(llm=ScriptedLLM([]))
    metric, _, _ = _metric([], VECTORS)
    assert metric.options.strictness == 3


@pytest.mark.parametrize("field", ["query", "answer"])
async def test_missing_input_raises(field):
    metric, _, _ = _metric([], VECTORS)

    with pytest.raises(ValueError, match=field):
        await metric.ameasure(SAMPLE.model_copy(update={field: ""}))


async def test_prompt_is_korean():
    metric, llm, _ = _metric([_response("재택근무는 며칠 가능한가요?")], VECTORS, strictness=1)

    await metric.ameasure(SAMPLE)

    prompt = llm.prompt(0)
    assert prompt.startswith("주어진 답변에 대한 질문을 생성하고")
    assert "예시 3" in prompt
    assert "\\u" not in prompt
    assert SAMPLE.answer in prompt
    assert prompt.rstrip().endswith("출력:")
