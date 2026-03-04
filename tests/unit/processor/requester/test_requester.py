# pylint: disable=missing-docstring
import re

import pytest
import responses
from requests import ConnectTimeout, HTTPError
from responses import matchers

from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [
    pytest.param(
        {"filter": "message", "requester": {"url": "http://mock-mock", "method": "GET"}},
        {"message": "the message"},
        {"message": "the message"},
        {"method": "GET", "url": "http://mock-mock", "status": 200},
        id="simple request",
    ),
    pytest.param(
        {"filter": "message", "requester": {"url": "${url}", "method": "GET"}},
        {"message": "the message", "url": "http://mock-mock"},
        {"message": "the message", "url": "http://mock-mock"},
        {"method": "GET", "url": "http://mock-mock", "status": 200},
        id="request with url from field",
    ),
    pytest.param(
        {"filter": "message", "requester": {"url": "${url}/${file}", "method": "GET"}},
        {"message": "the message", "url": "http://mock-mock", "file": "file.yml"},
        {"message": "the message", "url": "http://mock-mock", "file": "file.yml"},
        {"method": "GET", "url": "http://mock-mock/file.yml", "status": 200},
        id="request with url from different fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {"url": "${m\\\\y\\.url}/${my\\.file}", "method": "GET"},
        },
        {"message": "the message", "m\\y.url": "http://mock-mock", "my.file": "file.yml"},
        {"message": "the message", "m\\y.url": "http://mock-mock", "my.file": "file.yml"},
        {"method": "GET", "url": "http://mock-mock/file.yml", "status": 200},
        id="request with url from different escaped fields",
    ),
    pytest.param(
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
        id="post request with json",
    ),
    pytest.param(
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
        id="post request with json from fields",
    ),
    pytest.param(
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
        id="post request with complex json and url from dotted fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://${message.action\\.url}",
                "method": "POST",
                "json": {"${message.comp\\\\lex\\.key}": "${message.complex\\.value}"},
            },
        },
        {"message": {"action.url": "mock-mock", "comp\\lex.key": "key", "complex.value": "value"}},
        {"message": {"action.url": "mock-mock", "comp\\lex.key": "key", "complex.value": "value"}},
        {
            "method": "POST",
            "url": "http://mock-mock/",
            "match": [matchers.json_params_matcher({"key": "value"})],
            "content_type": "application/json",
            "status": 200,
        },
        id="post request with complex json and url from escaped dotted fields",
    ),
    pytest.param(
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
        id="get request with auth from kwargs",
    ),
    pytest.param(
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
        id="post request with templated data",
    ),
    pytest.param(
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
        id="parses json result to target field",
    ),
    pytest.param(
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
        id="parses text result to target field",
    ),
    pytest.param(
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
        id="parses json result with simple target field mapping",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "target_field": "message",  # will fail as it is already present
                "target_field_mapping": {"key1.key2.key3": "result.custom"},
            },
        },
        {"message": "the message"},
        {"message": "the message", "result": {"custom": "value"}, "tags": ["_requester_failure"]},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "json": {"key1": {"key2": {"key3": "value"}}},
            "content_type": "text/plain",
            "status": 200,
        },
        id="use target_field and target_field_mapping at the same time, with error in target_field",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "target_field_mapping": {"key1.key2.key3": "result.custom"},
                "overwrite_target": True,
            },
        },
        {"message": "the message", "result": {"custom", "preexisting"}},
        {"message": "the message", "result": {"custom": "value"}},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "json": {"key1": {"key2": {"key3": "value"}}},
            "content_type": "text/plain",
            "status": 200,
        },
        id="parses json result with simple target field mapping and overwrite target",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "target_field_mapping": {"key1.0.key2.key3": "result.custom"},
                "overwrite_target": True,
            },
        },
        {"message": "the message", "result": {"custom", "preexisting"}},
        {"message": "the message", "result": {"custom": "value"}},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "json": {"key1": [{"key2": {"key3": "value"}}]},
            "content_type": "text/plain",
            "status": 200,
        },
        id="parses json list result with simple target field mapping and overwrite target",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://mock-mock/",
                "method": "GET",
                "target_field": "result",
                "overwrite_target": True,
            },
        },
        {"message": "the message", "result": "preexisting"},
        {"message": "the message", "result": "the body"},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "body": "the body",
            "content_type": "text/plain",
            "status": 200,
        },
        id="parses text result to preexisting target field",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://${domain}/",
                "method": "GET",
                "json": {"${field1}": "the other ${field2}"},
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"message": "the message", "domain": "mock-mock", "field1": "key", "field2": "value"},
        {"message": "the message", "result": "the body"},
        {
            "method": "GET",
            "url": "http://mock-mock/",
            "body": "the body",
            "content_type": "text/plain",
            "status": 200,
        },
        id="deletes source fields",
    ),
    pytest.param(
        {
            "filter": "data",
            "requester": {
                "url": "http://localhost/",
                "method": "GET",
                "target_field": "data",
                "delete_source_fields": True,
                "merge_with_target": True,
            },
        },
        {"data": {"existing": "data"}},
        {"data": {"existing": "data", "new-data": {"dict": "value"}}},
        {
            "method": "GET",
            "url": "http://localhost/",
            "json": {"new-data": {"dict": "value"}},
            "content_type": "text/plain",
            "status": 200,
        },
        id="merge response with existing dict",
    ),
]

failure_test_cases = [
    pytest.param(
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
        ".*ProcessingWarning.*",
        id="handles HTTPError",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {"url": "http://failure_mock", "method": "GET", "timeout": 0.2},
        },
        {"message": "the message"},
        {"message": "the message", "tags": ["_requester_failure"]},
        {
            "method": "GET",
            "url": "http://failure_mock",
            "body": ConnectTimeout(),
            "content_type": "text/plain",
            "status": 200,
        },
        ".*ProcessingWarning.*",
        id="timout error",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {
                "url": "http://failure_mock",
                "method": "GET",
                "target_field": "result",
            },
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
        ".*FieldExistsWarning.*",
        id="does not overwrite if not permitted",
    ),
    pytest.param(
        {
            "filter": "message",
            "requester": {"url": "http://${missingfield}", "method": "GET"},
        },
        {"message": "the message"},
        {"message": "the message", "tags": ["_requester_missing_field_warning"]},
        {},
        ".*ProcessingWarning.*",
        id="errors on missing fields",
    ),
]  # testcase, rule, event, expected, mock, error_message


class TestRequester(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "requester",
        "rules": ["tests/testdata/unit/requester/rules"],
    }

    @responses.activate
    @pytest.mark.parametrize("rule, event, expected, response_kwargs", test_cases)
    def test_testcases(self, rule, event, expected, response_kwargs):
        responses.add(responses.Response(**response_kwargs))
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @responses.activate
    @pytest.mark.parametrize(
        "rule, event, expected, response_kwargs, error_message", failure_test_cases
    )
    def test_requester_testcases_failure_handling(
        self, rule, event, expected, response_kwargs, error_message
    ):
        if response_kwargs:
            responses.add(responses.Response(**response_kwargs))
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event == expected
