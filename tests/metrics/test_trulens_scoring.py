import json

import pytest

from chaejeom.metrics.trulens.scoring import (
    Judgment,
    ParseError,
    mean_graded_score,
    parse_score_and_reasons,
    re_configured_rating,
)


def test_json_path():
    j = parse_score_and_reasons('{"criteria": "기준", "supporting_evidence": "근거", "score": 2}')

    assert (j.score, j.criteria, j.supporting_evidence) == (2.0, "기준", "근거")
    assert j.normalized == pytest.approx(2 / 3)


def test_json_in_code_block():
    j = parse_score_and_reasons('```json\n{"criteria": "c", "supporting_evidence": "e", "score": 3}\n```')

    assert j.score == 3.0


def test_json_out_of_range_raises():
    with pytest.raises(ParseError):
        parse_score_and_reasons('{"criteria": "c", "supporting_evidence": "e", "score": 5}')


def test_json_non_numeric_score_is_unparsable():
    j = parse_score_and_reasons('{"criteria": "c", "supporting_evidence": "e", "score": "높음"}')

    assert j.score is None
    assert j.normalized is None


def test_text_path():
    response = "Criteria: 질의 전체와 관련 있는지\nSupporting Evidence: 연차 규정을 설명합니다.\n이월 규정은 없습니다.\nScore: 2"

    j = parse_score_and_reasons(response)

    assert j.score == 2
    assert j.criteria == "질의 전체와 관련 있는지"
    assert j.supporting_evidence.startswith("연차 규정을 설명합니다.\n이월 규정은 없습니다.")


def test_text_path_score_on_next_line():
    assert parse_score_and_reasons("Supporting Evidence: 근거\nScore:\n3").score == 3


def test_text_path_without_score_is_unparsable():
    assert parse_score_and_reasons("Supporting Evidence: 근거만 있음").score is None


def test_plain_rating_without_evidence():
    assert parse_score_and_reasons("2").score == 2


def test_json_after_text_with_digits():
    response = '1번과 2번 문장을 보면 0점은 아닙니다.\nJSON: {"criteria": "c", "supporting_evidence": "1번 문장", "score": 3}'

    j = parse_score_and_reasons(response)

    assert (j.score, j.supporting_evidence) == (3.0, "1번 문장")


@pytest.mark.parametrize(("score", "expected"), [(2, 2.0), ("2", 2.0), (" 1.5 ", 1.5), (True, None), ("높음", None)])
def test_json_score_only(score, expected):
    assert parse_score_and_reasons(json.dumps({"score": score})).score == expected


def test_json_without_score_falls_back_to_text():
    assert parse_score_and_reasons('Supporting Evidence: {"근거": 1}\nScore: 2').score == 2


@pytest.mark.parametrize(
    "response",
    [
        "Score: 2 (0~3 척도)",
        "Score: 2 (0～3 척도)",
        "Score: 2 (0 ~ 3)",
        "Score: 2점 (0에서 3 사이)",
        "Score: 2, 0에서 3까지의 척도",
        "Score: 2 (0부터 3까지)",
    ],
)
def test_korean_scale_notation_is_stripped(response):
    assert parse_score_and_reasons(response).score == 2


def test_no_minimum_number_from_whole_response():
    # Without a "Score:" line, upstream takes the smallest in-range number anywhere in the response (here 1).
    assert parse_score_and_reasons("1번 문장과 2번 문장이 관련 있어 3점입니다.").score is None


def test_score_line_without_number_is_unparsable():
    assert parse_score_and_reasons("Supporting Evidence: 근거\nScore: 높음").score is None
    assert parse_score_and_reasons("Score: 5").score is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("점수: 2", 2),
        ("0 to 3 척도에서 3", 3),
        ("1점 또는 2점", 1),
        ("2.7", 2),
    ],
)
def test_re_configured_rating(text, expected):
    assert re_configured_rating(text) == expected


def test_re_configured_rating_without_number_raises():
    with pytest.raises(ParseError):
        re_configured_rating("관련 있음")


def test_mean_graded_score_skips_unparsable():
    assert mean_graded_score([Judgment(3), Judgment(None), Judgment(1)]) == 2
    assert mean_graded_score([Judgment(None)]) is None
