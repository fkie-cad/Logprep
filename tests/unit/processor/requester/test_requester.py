# pylint: disable=missing-docstring
import pytest
import responses
from logprep.processor.base.exceptions import DuplicationError, ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = [
    (
        "simple request",
        {"filter": "message", "requester": {"url": "http://mock-mock", "method": "GET"}},
        {"message": "the message"},
        {"message": "the message"},
        {"method": "GET", "url": "http://mock-mock", "status": 200},
    )
]  # testcase, rule, event, expected

failure_test_cases = []  # testcase, rule, event, expected


class TestRequester(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "requester",
        "specific_rules": ["tests/testdata/unit/requester/specific_rules"],
        "generic_rules": ["tests/testdata/unit/requester/generic_rules"],
    }

    @responses.activate
    @pytest.mark.parametrize("testcase, rule, event, expected, response", test_cases)
    def test_testcases(
        self, testcase, rule, event, expected, response
    ):  # pylint: disable=unused-argument
        responses.add(responses.Response(**response))
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase

    @responses.activate
    def test_process(self):
        responses.add(responses.Response(**{"url": "http://the-url", "method": "GET"}))
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "event_id": "1234",
            "message": "user root logged in",
        }
        count = self.object.metrics.number_of_processed_events
        self.object.process(document)
