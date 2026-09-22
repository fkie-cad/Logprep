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
        id="splits without delimiter on whitespace",
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
        id="splits one item with multiple delimiter and no drop empty",
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
        id="splits one item with multiple delimiter and empty fields",
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
        id="splits with delimiter",
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
        id="splits one item with delimiter",
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
        id="splits one item with multiple delimiter and drop empty",
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
        id="splits one item with multiple delimiter and whitespace",
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
        id="splits one item with multiple delimiter and newline",
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
        id="splits one item with multiple delimiter and whitespaces only in front",
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
        id="splits with multiple delimiters and whitespace only in front",
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
        id="splits without delimiter on whitespace with no string",
    ),
    pytest.param(
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "message"},
        },
        {"message": "this is the message"},
        {"message": "this is the message", "tags": ["_string_splitter_failure"]},
        ".*FieldExistsWarning.*",
        id="splits without delimiter on whitespace with existing field",
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
