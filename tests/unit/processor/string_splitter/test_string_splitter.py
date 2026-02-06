# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
import re

import pytest

from tests.unit.processor.base import BaseProcessorTestCase


class TestStringSplitter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(
        ["rule", "event", "expected"],
        [
            pytest.param(
                {
                    "filter": "message",
                    "string_splitter": {
                        "source_fields": ["message"],
                        "target_field": "result",
                        "remove_whitespace": True,
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
                        "remove_whitespace": True,
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
                        "remove_whitespace": True,
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
                        "remove_whitespace": True,
                    },
                },
                {"message": ",,this,,"},
                ["this"],
                id="splits_one_item_with_multiple_delimiter_and_remove_whitespace",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "string_splitter": {
                        "source_fields": ["message"],
                        "target_field": "result",
                        "delimiter": ",",
                        "remove_whitespace": False,
                    },
                },
                {"message": ",,this,,"},
                ["", "", "this", "", ""],
                id="splits_one_item_with_multiple_delimiter_and_no_remove_whitespace",
            ),
        ],
    )
    def test_testcases(self, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event["result"] == expected

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
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event == expected
