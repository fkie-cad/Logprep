# pylint: disable=missing-docstring

from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.dissector.test_dissector import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.dissector.test_dissector import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestDissector(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_dissector",
        "rules": ["tests/testdata/unit/dissector/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert log_event.data == expected, testcase
