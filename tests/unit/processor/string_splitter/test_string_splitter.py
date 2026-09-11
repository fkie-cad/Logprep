# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
import re

import pytest

from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "drop_empty": True,
            },
        },
        {"message": "this is the message"},
        ["this", "is", "the", "message"],
        id="splits_without_delimiter_on_whitespace",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": False,
            },
        },
        {"message": ",,this,,"},
        ["", "", "this", "", ""],
        id="splits_one_item_with_multiple_delimiter_and_no_drop_empty",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": " , ,this, ,"},
        ["this"],
        id="splits_one_item_with_multiple_delimiter_and_empty_fields",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ", ",
                "drop_empty": True,
            },
        },
        {"message": "this, is, the, message"},
        ["this", "is", "the", "message"],
        id="splits_with_delimiter",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": "this,"},
        ["this"],
        id="splits_one_item_with_delimiter",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": ",,this,,"},
        ["this"],
        id="splits_one_item_with_multiple_delimiter_and_drop_empty",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": ",, this , , "},
        [" this "],
        id="splits_one_item_with_multiple_delimiter_and_whitespace",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": "\n,,this,\t, "},
        ["this"],
        id="splits_one_item_with_multiple_delimiter_and_newline",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": ",, this, , "},
        [" this"],
        id="splits_one_item_with_multiple_delimiter_and_whitespaces_only_in_front",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        {"message": "hello , world,this, is a very complex,\n , and even multiline, text,,, "},
        ["hello ", " world", "this", " is a very complex", " and even multiline", " text"],
        id="splits_with_multiple_delimiters_and_whitespace_only_in_front",
    ),
)

failure_test_cases = normalize_test_cases(
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "result"},
        },
        {"message": ["this", "is", "the", "message"]},
        {"message": ["this", "is", "the", "message"], "tags": ["_string_splitter_failure"]},
        ".*ProcessingWarning.*",
        id="splits_without_delimiter_on_whitespace_with_no_string",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "message"},
        },
        {"message": "this is the message"},
        {"message": "this is the message", "tags": ["_string_splitter_failure"]},
        ".*FieldExistsWarning.*",
        id="splits_without_delimiter_on_whitespace_with_existing_field",
    ),
)


class TestStringSplitter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event["result"] == expected

    @pytest.mark.parametrize(["rule", "event", "expected", "error_message"], failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event == expected
