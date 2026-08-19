# pylint: disable=missing-docstring,protected-access
import typing
from importlib.metadata import version
from unittest import mock

import aiohttp
import pytest
from aiohttp import web

from logprep.ng.util.getter import (
    GetterFactory,
    HttpGetter,
    RefreshableGetter,
    RefreshableGetterError,
)
from logprep.util.credentials import CredentialsEnvNotFoundError


@pytest.fixture(autouse=True)
def reset_refreshable_getters():
    RefreshableGetter.reset()
    HttpGetter._credentials_registry.clear()
    yield
    RefreshableGetter.reset()
    HttpGetter._credentials_registry.clear()


class TestHttpGetter:
    def test_factory_returns_http_getter_for_http(self):
        http_getter = GetterFactory.from_string("http://testfile.json")

        assert isinstance(http_getter, HttpGetter)

    def test_factory_returns_http_getter_for_https(self):
        http_getter = GetterFactory.from_string("https://testfile.json")

        assert isinstance(http_getter, HttpGetter)

    async def test_get_json_returns_json_content(self, aiohttp_server):
        async def handler(_: web.Request) -> web.Response:
            return web.json_response({"key": "value"})

        app = web.Application()
        app.router.add_get("/data.json", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data.json")))

        assert await http_getter.get_json() == {"key": "value"}

    async def test_sends_logprep_version_in_user_agent(self, aiohttp_server):
        received_user_agent = None

        async def handler(request: web.Request) -> web.Response:
            nonlocal received_user_agent
            received_user_agent = request.headers.get("User-Agent")

            return web.Response(
                text="content",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data")))

        await http_getter.get()

        assert received_user_agent == f"Logprep version {version('logprep')}"

    async def test_get_from_target_returns_normalized_content_type(
        self,
        aiohttp_server,
    ):
        async def handler(_: web.Request) -> web.Response:
            return web.json_response({"key": "value"})

        app = web.Application()
        app.router.add_get("/data.json", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data.json")))

        content, content_type, was_modified = await http_getter._get_from_target()

        assert content == b'{"key": "value"}'
        assert content_type == "application/json"
        assert was_modified is True

    async def test_retries_three_times_after_retryable_status(
        self,
        aiohttp_server,
    ):
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            return web.Response(status=500)

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data")))

        with pytest.raises(RefreshableGetterError):
            await http_getter.get()

        assert request_count == 4

    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    async def test_retries_retryable_status_codes(
        self,
        status,
        aiohttp_server,
    ):
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            return web.Response(status=status)

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data")))

        with pytest.raises(RefreshableGetterError):
            await http_getter.get()

        assert request_count == 4

    async def test_succeeds_after_retryable_failures(self, aiohttp_server):
        statuses = [500, 502, 200]
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count

            status = statuses[request_count]
            request_count += 1

            if status != 200:
                return web.Response(status=status)

            return web.json_response({"key": "value"})

        app = web.Application()
        app.router.add_get("/data.json", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data.json")))

        assert await http_getter.get_json() == {"key": "value"}
        assert request_count == 3

    async def test_does_not_retry_non_retryable_status(self, aiohttp_server):
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data")))

        with pytest.raises(RefreshableGetterError):
            await http_getter.get()

        assert request_count == 1

    async def test_getter_etag_keeps_cached_content_on_304(
        self,
        aiohttp_server,
    ):
        request_count = 0
        if_none_match_headers = []

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count

            request_count += 1
            if_none_match_headers.append(request.headers.get("If-None-Match"))

            if request_count == 1:
                return web.json_response(
                    {"key": "content 1"},
                    headers={"ETag": "1"},
                )

            if request_count == 2:
                return web.Response(
                    status=304,
                    headers={"ETag": "1"},
                )

            return web.json_response(
                {"key": "content 2"},
                headers={"ETag": "2"},
            )

        app = web.Application()
        app.router.add_get("/data.json", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data.json")))

        assert http_getter.hash is None

        assert await http_getter.get_json() == {"key": "content 1"}
        assert http_getter.hash == "1"

        assert await http_getter.get_json() == {"key": "content 1"}
        assert http_getter.hash == "1"

        assert await http_getter.get_json() == {"key": "content 2"}
        assert http_getter.hash == "2"

        assert if_none_match_headers == [
            None,
            "1",
            "1",
        ]

    async def test_raises_credentials_error_on_401_without_credentials_file(
        self,
        aiohttp_server,
    ):
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            return web.Response(status=401)

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        http_getter = GetterFactory.from_string(str(server.make_url("/data")))

        with pytest.raises(CredentialsEnvNotFoundError):
            await http_getter.get()

        assert request_count == 1

    def test_converts_basic_auth_to_authorization_header(self):
        http_getter = GetterFactory.from_string("https://example.test/data")

        session = mock.MagicMock()
        session.auth = ("username", "password")
        session.headers = {}
        session.verify = True
        session.cert = None

        credentials = mock.MagicMock()
        credentials.get_session.return_value = session

        HttpGetter._credentials_registry["https://example.test"] = credentials

        request_kwargs = http_getter._get_aiohttp_request_kwargs_sync()

        assert request_kwargs == {
            "headers": {
                "Authorization": aiohttp.encode_basic_auth(
                    "username",
                    "password",
                )
            },
        }

    def test_converts_authorization_header_to_aiohttp_headers(self):
        http_getter = GetterFactory.from_string("https://example.test/data")

        session = mock.MagicMock()
        session.auth = None
        session.headers = {"Authorization": "Bearer token"}
        session.verify = True
        session.cert = None

        credentials = mock.MagicMock()
        credentials.get_session.return_value = session

        HttpGetter._credentials_registry["https://example.test"] = credentials

        request_kwargs = http_getter._get_aiohttp_request_kwargs_sync()

        assert request_kwargs == {
            "headers": {"Authorization": "Bearer token"},
        }

    def test_disables_ssl_verification_if_configured(self):
        ssl_context = HttpGetter._create_ssl_context(
            verify=False,
            cert=None,
        )

        assert ssl_context is False

    def test_creates_ssl_context_with_ca_and_client_certificate(self):
        ssl_context = mock.MagicMock()

        with mock.patch(
            "logprep.ng.util.getter.ssl.create_default_context",
            return_value=ssl_context,
        ) as create_default_context:
            result = HttpGetter._create_ssl_context(
                verify="/path/to/ca.pem",
                cert=("/path/to/client.pem", "/path/to/client.key"),
            )

        create_default_context.assert_called_once_with(
            cafile="/path/to/ca.pem",
        )
        ssl_context.load_cert_chain.assert_called_once_with(
            certfile="/path/to/client.pem",
            keyfile="/path/to/client.key",
        )
        assert result is ssl_context

    def test_credentials_registry_is_shared_between_http_getters(self):
        first_getter: HttpGetter = typing.cast(
            HttpGetter, GetterFactory.from_string("https://example.test/one")
        )
        second_getter: HttpGetter = typing.cast(
            HttpGetter, GetterFactory.from_string("https://example.test/two")
        )

        credentials = mock.MagicMock()
        HttpGetter._credentials_registry["https://example.test"] = credentials

        assert first_getter._credentials_registry is second_getter._credentials_registry
        assert first_getter._credentials_registry["https://example.test"] is credentials
        assert second_getter._credentials_registry["https://example.test"] is credentials


class TestRefreshableGetter:
    async def test_refresh_continues_after_callback_failure(self, caplog):
        getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )

        getter.shared.initialized = True
        getter.shared.refresh_interval = 0
        getter.shared.timeout_interval = 60

        failing_callback = mock.AsyncMock(side_effect=RuntimeError("callback failed"))
        succeeding_callback = mock.AsyncMock()

        getter.add_callback("failing", failing_callback)
        getter.add_callback("succeeding", succeeding_callback)

        with mock.patch.object(
            HttpGetter,
            "_update_cache",
            new=mock.AsyncMock(return_value=True),
        ):
            await getter._refresh()

        failing_callback.assert_awaited_once()
        succeeding_callback.assert_awaited_once()

        assert getter.shared.refreshing is False
        assert "refresh callback failed" in caplog.text

    async def test_refresh_callback_reads_updated_cache_without_refreshing_again(self):
        getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )

        getter.shared.initialized = True
        getter.shared.refresh_interval = 0
        getter.shared.timeout_interval = 60
        getter.cache = b'{"value": 1}'
        getter.content_type = "application/json"

        callback_result = None

        async def callback():
            nonlocal callback_result
            callback_result = await getter.get_json()

        getter.add_callback("test", callback)

        update_cache = mock.AsyncMock(return_value=True)

        with mock.patch.object(
            HttpGetter,
            "_update_cache",
            new=update_cache,
        ):
            await getter._refresh()

        update_cache.assert_awaited_once()
        assert callback_result == {"value": 1}
