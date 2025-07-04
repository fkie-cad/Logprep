# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=import-error

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "writes missing root-key in the missing_fields Field",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key2"],
                "target_field": "missing_fields",
            },
        },
        {
            "testkey": "key1_value",
            "_index": "value",
        },
        {
            "testkey": "key1_value",
            "_index": "value",
            "missing_fields": ["key2"],
        },
    ),
]


class TestKeyChecker(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_key_checker",
        "rules": ["tests/testdata/unit/key_checker/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected
