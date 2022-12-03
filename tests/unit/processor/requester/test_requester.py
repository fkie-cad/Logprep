# pylint: disable=missing-docstring
from unittest import mock

import pytest
import responses
from requests import HTTPError
from responses import matchers, Response

from logprep.processor.base.exceptions import DuplicationError, ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

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
    (
        "request with url from different fields",
        {"filter": "message", "requester": {"url": "${url}/${file}", "method": "GET"}},
        {"message": "the message", "url": "http://mock-mock", "file": "file.yml"},
        {"message": "the message", "url": "http://mock-mock", "file": "file.yml"},
        {"method": "GET", "url": "http://mock-mock/file.yml", "status": 200},
    ),
    (
        "post request with json",
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock",
                "method": "POST",
                "json": {"the": "json value"},
            },
        },
        {"message": "the message", "url": "http://mock-mock"},
        {"message": "the message", "url": "http://mock-mock"},
        {"method": "POST", "url": "http://mock-mock/", "status": 200},
    ),
    (
        "post request with json from fields",
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock",
                "method": "POST",
                "json": {"the": "${message}"},
            },
        },
        {"message": "the message", "url": "http://mock-mock"},
        {"message": "the message", "url": "http://mock-mock"},
        {
            "method": "POST",
            "url": "http://mock-mock/",
            "match": [matchers.json_params_matcher({"the": "the message"})],
            "status": 200,
        },
    ),
    (
        "post request with complex json and url from dotted fields",
        {
            "filter": "message",
            "requester": {
                "url": "http://${message.url}",
                "method": "POST",
                "json": {"${message.key}": "${message.value}"},
            },
        },
        {"message": {"url": "mock-mock", "key": "keyvalue", "value": "valuevalue"}},
        {"message": {"url": "mock-mock", "key": "keyvalue", "value": "valuevalue"}},
        {
            "method": "POST",
            "url": "http://mock-mock/",
            "match": [matchers.json_params_matcher({"keyvalue": "valuevalue"})],
            "content_type": "application/json",
            "status": 200,
        },
    ),
    (
        "get request with auth from kwargs",
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "auth": ["username", "password"],
            },
        },
        {"message": "the message"},
        {"message": "the message"},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "status": 200,
        },
    ),
    (
        "post request with templated data",
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "data": "fielddata ${message}",
            },
        },
        {"message": "the message"},
        {"message": "the message"},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "status": 200,
        },
    ),
    (
        "parses json result to target field",
        {
            "filter": "message",
            "requester": {"url": "http://mock-mock/", "method": "GET", "target_field": "result"},
        },
        {"message": "the message"},
        {"message": "the message", "result": {"testkey": "testresult"}},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "json": {"testkey": "testresult"},
            "content_type": "application/json",
            "status": 200,
        },
    ),
    (
        "parses text result to target field",
        {
            "filter": "message",
            "requester": {"url": "http://mock-mock/", "method": "GET", "target_field": "result"},
        },
        {"message": "the message"},
        {"message": "the message", "result": "the body"},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "body": "the body",
            "content_type": "text/plain",
            "status": 200,
        },
    ),
    (
        "parses json result with simple target field mapping",
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "target_field_mapping": {"key1.key2.key3": "result.custom"},
            },
        },
        {"message": "the message"},
        {"message": "the message", "result": {"custom": "value"}},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "json": {"key1": {"key2": {"key3": "value"}}},
            "content_type": "text/plain",
            "status": 200,
        },
    ),
]  # testcase, rule, event, expected, response

failure_test_cases = [
    (
        "handles HTTPError",
        {"filter": "message", "requester": {"url": "http://failure_mock", "method": "GET"}},
        {"message": "the message"},
        {"message": "the message", "tags": ["_requester_failure"]},
        {
            "method": "GET",
            "url": "http://failure_mock",
            "body": HTTPError("404"),
            "content_type": "text/plain",
            "status": 404,
        },
    ),
    (
        "does not overwrite if not permitted",
        {
            "filter": "message",
            "requester": {"url": "http://failure_mock", "method": "GET", "target_field": "result"},
        },
        {"message": "the message", "result": "preexisting"},
        {"message": "the message", "result": "preexisting", "tags": ["_requester_failure"]},
        {
            "method": "GET",
            "url": "http://failure_mock",
            "body": "the body",
            "content_type": "text/plain",
            "status": 200,
        },
    ),
    (
        "errors on missing fields",
        {
            "filter": "message",
            "requester": {"url": "http://${missingfield}", "method": "GET"},
        },
        {"message": "the message"},
        {"message": "the message", "tags": ["_requester_failure"]},
        {},
    ),
]  # testcase, rule, event, expected, mock


class TestRequester(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "requester",
        "specific_rules": ["tests/testdata/unit/requester/specific_rules"],
        "generic_rules": ["tests/testdata/unit/requester/generic_rules"],
    }

    @responses.activate
    @pytest.mark.parametrize("testcase, rule, event, expected, response_kwargs", test_cases)
    def test_testcases(
        self, testcase, rule, event, expected, response_kwargs
    ):  # pylint: disable=unused-argument
        responses.add(responses.Response(**response_kwargs))
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @responses.activate
    @pytest.mark.parametrize("testcase, rule, event, expected, response_kwargs", failure_test_cases)
    def test_requester_testcases_failure_handling(
        self, testcase, rule, event, expected, response_kwargs
    ):
        if response_kwargs:
            responses.add(responses.Response(**response_kwargs))
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
        _ = self.object.metrics.number_of_processed_events
        self.object.process(document)
