# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [
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
        id="splits_without_explicit_set_delimiter_on_whitespace",
    ),
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
                "drop_empty": False,
            },
        },
        {"message": ",,this,,"},
        ["", "", "this", "", ""],
        id="splits_one_item_with_multiple_delimiter_and_no_drop_empty",
    ),
]


class TestStringSplitter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected"], test_cases)
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data["result"] == expected

    @pytest.mark.parametrize(
        ["rule", "event", "expected", "error_message"],
        [
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
        ],
    )
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected
