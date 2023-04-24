# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "parses iso8601 without pattern",
        {
            "filter": "message",
            "timestamper": {"source_fields": ["message"], "target_field": "@timestamp"},
        },
        {
            "message": "2009-06-15 13:45:30Z",
        },
        {"message": "2009-06-15 13:45:30Z", "@timestamp": "2009-06-15T13:45:30+00:00"},
    )
]

failure_test_cases = []  # testcase, rule, event, expected


class TestTimestamper(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "timestamper",
        "specific_rules": [],
        "generic_rules": [],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
