# pylint: disable=missing-docstring

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [
    (
        "splits without delimeter on whitespace",
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "result"},
        },
        {"message": "this is the message"},
        {"message": "this is the message", "result": ["this", "is", "the", "message"]},
    ),
    (
        "splits with delimeter",
        {
            "filter": "message",
            "string_splitter": {
                "source_fields": ["message"],
                "target_field": "result",
                "delimiter": ", ",
            },
        },
        {"message": "this, is, the, message"},
        {"message": "this, is, the, message", "result": ["this", "is", "the", "message"]},
    ),
]  # testcase, rule, event, expected

failure_test_cases = [
    (
        "splits without delimeter on whitespace",
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "result"},
        },
        {"message": ["this", "is", "the", "message"]},
        {"message": ["this", "is", "the", "message"], "tags": ["_string_splitter_failure"]},
        ".*ProcessingWarning.*",
    ),
    (
        "splits without delimeter on whitespace",
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "message"},
        },
        {"message": "this is the message"},
        {"message": "this is the message", "tags": ["_string_splitter_failure"]},
        ".*FieldExistsWarning.*",
    ),
]  # testcase, rule, event, expected, error_message


class TestStringSplitter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert log_event.data == expected, testcase
