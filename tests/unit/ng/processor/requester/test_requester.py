# pylint: disable=missing-docstring

import pytest
import responses

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [
    (
        "simple request",
        {"filter": "message", "requester": {"url": "http://mock-mock", "method": "GET"}},
        {"message": "the message"},
        {"message": "the message"},
        {"method": "GET", "url": "http://mock-mock", "status": 200},
    ),
    (
        "request with url from field",
        {"filter": "message", "requester": {"url": "${url}", "method": "GET"}},
        {"message": "the message", "url": "http://mock-mock"},
        {"message": "the message", "url": "http://mock-mock"},
        {"method": "GET", "url": "http://mock-mock", "status": 200},
    ),
]  # testcase, rule, event, expected, response_mock


class TestRequester(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_requester",
        "rules": ["tests/testdata/unit/requester/rules"],
    }

    @responses.activate
    @pytest.mark.parametrize("testcase, rule, event, expected, response_mock", test_cases)
    def test_testcases(
        self, testcase, rule, event, expected, response_mock
    ):  # pylint: disable=unused-argument
        responses.add(
            getattr(responses, response_mock["method"]),
            response_mock["url"],
            status=response_mock["status"],
        )
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected
