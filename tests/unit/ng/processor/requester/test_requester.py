# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest
import responses

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.requester.test_requester import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.requester.test_requester import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestRequester(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_requester",
        "rules": ["tests/testdata/unit/requester/rules"],
    }

    @responses.activate
    @pytest.mark.parametrize("testcase, rule, event, expected, response_kwargs", test_cases)
    def test_testcases(self, testcase, rule, event, expected, response_kwargs):
        responses.add(responses.Response(**response_kwargs))
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected, testcase

    @responses.activate
    @pytest.mark.parametrize(
        "testcase, rule, event, expected, response_kwargs, error_message", failure_test_cases
    )
    def test_requester_testcases_failure_handling(
        self, testcase, rule, event, expected, response_kwargs, error_message
    ):
        if response_kwargs:
            responses.add(responses.Response(**response_kwargs))
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected, testcase
