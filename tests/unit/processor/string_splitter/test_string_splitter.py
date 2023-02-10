# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


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
                "delimeter": ", ",
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
    ),
    (
        "splits without delimeter on whitespace",
        {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "message"},
        },
        {"message": "this is the message"},
        {"message": "this is the message", "tags": ["_string_splitter_failure"]},
    ),
]  # testcase, rule, event, expected


class TestStringSplitter(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "string_splitter",
        "specific_rules": ["tests/testdata/unit/string_splitter/specific/"],
        "generic_rules": ["tests/testdata/unit/string_splitter/generic/"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
