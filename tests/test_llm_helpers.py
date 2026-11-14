import pytest
from utils.llm_helpers import parse_json_response


def test_parses_json_fence():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}


def test_parses_bare_fence():
    assert parse_json_response('```\n{"a": 1}\n```') == {"a": 1}


def test_parses_plain_json_with_whitespace():
    assert parse_json_response('   {"a": 1}  \n') == {"a": 1}


def test_parses_json_list():
    assert parse_json_response("[1, 2, 3]") == [1, 2, 3]


def test_invalid_json_raises_value_error():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_response("Sure! Here are the candidates...")


def test_fence_with_nothing_after_raises_value_error():
    with pytest.raises(ValueError):
        parse_json_response("```json")