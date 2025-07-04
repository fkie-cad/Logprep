# pylint: disable=missing-docstring

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "calculates diff between timestamps",
        {
            "filter": "message",
            "timestamp_differ": {
                "diff": "${timestamp_end} - ${@timestamp}",
                "target_field": "duration",
            },
        },
        {
            "message": "test message",
            "@timestamp": "2022-01-01T10:00:00Z",
            "timestamp_end": "2022-01-01T10:00:05Z",
        },
        {
            "message": "test message",
            "@timestamp": "2022-01-01T10:00:00Z",
            "timestamp_end": "2022-01-01T10:00:05Z",
            "duration": "5.0",
        },
    ),
]


class TestTimestampDiffer(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_timestamp_differ",
        "rules": ["tests/testdata/unit/timestamp_differ/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected
