# pylint: disable=missing-docstring

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase

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
        {"message": "2009-06-15 13:45:30Z", "@timestamp": "2009-06-15T13:45:30Z"},
    ),
    (
        "parses iso8601 to default target field",
        {
            "filter": "message",
            "timestamper": {"source_fields": ["message"]},
        },
        {
            "message": "2009-06-15 13:45:30Z",
        },
        {"message": "2009-06-15 13:45:30Z", "@timestamp": "2009-06-15T13:45:30Z"},
    ),
]


class TestTimestamper(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_timestamper",
        "rules": ["tests/testdata/unit/timestamper/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected
