# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import json
import re
from contextlib import asynccontextmanager
from copy import deepcopy
from unittest import mock
from urllib.parse import urlsplit

import aiohttp
import pytest
import requests
from aiohttp import web

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.requester.processor import Requester
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.requester.test_requester import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.requester.test_requester import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)

failure_test_cases = [
    deepcopy(non_ng_failure_test_cases[0]),  # HTTP error
    deepcopy(non_ng_failure_test_cases[2]),  # FieldExistsWarning
]

timeout_test_case = deepcopy(non_ng_failure_test_cases[1].values)
missing_field_test_case = deepcopy(non_ng_failure_test_cases[3].values)


@pytest.fixture
def request_server(aiohttp_server):
    @asynccontextmanager
    async def make_server(response_kwargs):
        calls = []

        async def handler(request: web.Request) -> web.Response:
            body = await request.read()

            prepared_request = requests.Request(
                method=request.method,
                url=f"{request.scheme}://{request.host}{request.rel_url}",
                headers=dict(request.headers),
                data=body,
            ).prepare()

            calls.append(prepared_request)

            status = response_kwargs.get("status", 200)
            content_type = response_kwargs.get("content_type")

            if "json" in response_kwargs:
                body = json.dumps(response_kwargs["json"]).encode()
            else:
                response_body = response_kwargs.get("body", b"")

                if isinstance(response_body, bytes):
                    body = response_body
                elif isinstance(response_body, str):
                    body = response_body.encode()
                else:
                    body = b""

            return web.Response(
                body=body,
                status=status,
                content_type=content_type,
            )

        app = web.Application()
        app.router.add_route("*", "/{path_info:.*}", handler)

        server = await aiohttp_server(app)

        yield server, calls

    return make_server


def _replace_request_endpoint(value, source_url: str, target_url: str):
    source = urlsplit(source_url)
    target = urlsplit(target_url)

    if isinstance(value, dict):
        return {
            key: _replace_request_endpoint(item, source_url, target_url)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_replace_request_endpoint(item, source_url, target_url) for item in value]

    if isinstance(value, str):
        source_base_url = f"{source.scheme}://{source.netloc}"
        target_base_url = f"{target.scheme}://{target.netloc}"

        return value.replace(source_base_url, target_base_url).replace(
            source.netloc,
            target.netloc,
        )

    return value


def _prepare_testcase(rule, event, expected, response_kwargs, server):
    source_url = response_kwargs["url"]
    target_url = f"http://127.0.0.1:{server.port}"

    return (
        _replace_request_endpoint(rule, source_url, target_url),
        _replace_request_endpoint(event, source_url, target_url),
        _replace_request_endpoint(expected, source_url, target_url),
    )


def _assert_request(response_kwargs: dict, calls: list[requests.PreparedRequest]) -> None:
    assert len(calls) == 1

    call = calls[0]

    expected_url = urlsplit(response_kwargs["url"])
    actual_url = urlsplit(call.url)

    assert call.method == response_kwargs["method"]
    assert actual_url.path == (expected_url.path or "/")
    assert actual_url.query == expected_url.query

    for matcher in response_kwargs.get("match", []):
        matches, reason = matcher(call)
        assert matches, reason


class TestRequester(BaseProcessorTestCase[Requester]):
    CONFIG: dict = {
        "type": "requester",
        "rules": ["tests/testdata/unit/requester/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected, response_kwargs", test_cases)
    async def test_testcases(
        self,
        rule,
        event,
        expected,
        response_kwargs,
        request_server,
    ):
        async with request_server(response_kwargs) as (server, calls):
            rule, event, expected = _prepare_testcase(
                rule,
                event,
                expected,
                response_kwargs,
                server,
            )
            event = LogEvent(event, original=b"", input_meta=InputMeta())

            async with self.create_and_setup_processor(override_shared=True):
                await self._load_rule(rule)
                await self.object.process(event)

        assert event.data == expected
        _assert_request(response_kwargs, calls)

    @pytest.mark.parametrize(
        "rule, event, expected, response_kwargs, error_message",
        failure_test_cases,
    )
    async def test_requester_testcases_failure_handling(
        self,
        rule,
        event,
        expected,
        response_kwargs,
        error_message,
        request_server,
    ):
        async with request_server(response_kwargs) as (server, calls):
            rule, event, expected = _prepare_testcase(
                rule,
                event,
                expected,
                response_kwargs,
                server,
            )
            event = LogEvent(event, original=b"", input_meta=InputMeta())

            async with self.create_and_setup_processor(override_shared=True):
                await self._load_rule(rule)
                result = await self.object.process(event)

        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected
        _assert_request(response_kwargs, calls)

    async def test_handles_connection_timeout(self):
        rule, event, expected, _, error_message = timeout_test_case

        event = LogEvent(event, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor(override_shared=True):
            await self._load_rule(rule)

            with mock.patch.object(
                self.object._session,
                "request",
                side_effect=aiohttp.ConnectionTimeoutError(),
            ) as request_mock:
                result = await self.object.process(event)

            request_mock.assert_called_once()

        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected

    async def test_errors_on_missing_fields(self):
        rule, event, expected, _, error_message = missing_field_test_case

        event = LogEvent(event, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor(override_shared=True):
            await self._load_rule(rule)
            result = await self.object.process(event)

        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected

    async def test_has_async_io(self):
        assert await self.object.has_asyncio() is True

    async def test_setup_and_shutdown_http_session(self):
        instance = self._create_test_instance(deepcopy(self.CONFIG))

        assert instance._session is None

        await instance.setup()
        session = instance._session

        try:
            assert isinstance(session, aiohttp.ClientSession)
            assert session.closed is False
        finally:
            await instance.shut_down()

        assert session.closed is True
        assert instance._session is None
