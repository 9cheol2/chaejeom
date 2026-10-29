import pytest

from chaejeom.schema import EvalSample


def test_contexts_from_plain_strings():
    sample = EvalSample(query="질문", contexts=["첫 문맥", "둘째 문맥"], answer="답변")

    assert [c.id for c in sample.contexts] == ["c1", "c2"]
    assert [c.rank for c in sample.contexts] == [1, 2]
    assert sample.contexts[1].text == "둘째 문맥"


def test_context_id_and_rank_are_optional():
    sample = EvalSample(contexts=[{"text": "가"}, {"id": 7, "text": "나"}, {"text": "다", "rank": 9}])

    assert [(c.id, c.rank) for c in sample.contexts] == [("c1", 1), ("7", 2), ("c3", 9)]


def test_all_fields_optional():
    sample = EvalSample()

    assert (sample.query, sample.contexts, sample.answer, sample.id, sample.metadata) == ("", [], "", None, {})


@pytest.mark.parametrize(
    "row",
    [
        {"user_input": "질문", "retrieved_contexts": ["문맥"], "response": "답변"},
        {"input": "질문", "retrieval_context": ["문맥"], "actual_output": "답변"},
    ],
)
def test_ragas_and_deepeval_field_names(row):
    sample = EvalSample.model_validate(row)

    assert (sample.query, sample.contexts[0].text, sample.answer) == ("질문", "문맥", "답변")


def test_sample_id_and_metadata():
    sample = EvalSample.model_validate({"id": 12, "query": "질문", "metadata": {"retriever": "bm25"}})

    assert sample.id == "12"
    assert sample.metadata == {"retriever": "bm25"}


def test_contexts_as_objects_kept():
    sample = EvalSample(
        query="질문",
        contexts=[{"id": "doc-7", "text": "문맥", "rank": 3}],
        answer="답변",
    )

    assert sample.contexts[0].id == "doc-7"
    assert sample.contexts[0].rank == 3
