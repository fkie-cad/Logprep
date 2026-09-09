# pylint: disable=missing-docstring,protected-access
import asyncio
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
from logprep.util.async_scheduler import AsyncScheduler
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

    async def test_concurrent_cache_updates_share_single_request(self):
        first_getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )
        second_getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )

        first_getter.shared.initialized = True
        first_getter.shared.refresh_interval = 0
        first_getter.shared.timeout_interval = 60

        request_started = asyncio.Event()
        release_request = asyncio.Event()

        async def get_from_target():
            request_started.set()
            await release_request.wait()
            return b'{"value": 1}', "application/json", True

        with mock.patch.object(
            HttpGetter,
            "_get_from_target",
            new=mock.AsyncMock(side_effect=get_from_target),
        ) as get_from_target_mock:
            first_request = asyncio.create_task(first_getter.get_json())

            await request_started.wait()

            second_request = asyncio.create_task(second_getter.get_json())

            await asyncio.sleep(0)

            release_request.set()

            first_result, second_result = await asyncio.gather(
                first_request,
                second_request,
            )

        assert first_result == {"value": 1}
        assert second_result == {"value": 1}
        assert get_from_target_mock.await_count == 1

    async def test_remove_callbacks_for_tag_removes_orphaned_cached_target(self):
        getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )

        getter.shared.cache = b'{"value": 1}'
        getter.shared.scheduler = AsyncScheduler()

        callback = mock.AsyncMock()
        getter.add_callback("processor", callback)

        assert getter.target in RefreshableGetter._target_to_data_caches
        assert getter.shared.cache is not None
        assert getter.shared.scheduler is not None

        RefreshableGetter.remove_callbacks_for_tag("processor")

        assert getter.target not in RefreshableGetter._target_to_data_caches

    async def test_remove_callbacks_for_tag_keeps_target_used_by_other_tag(self):
        getter: HttpGetter = typing.cast(
            HttpGetter,
            GetterFactory.from_string("https://example.test/data"),
        )

        getter.shared.cache = b'{"value": 1}'
        getter.shared.scheduler = AsyncScheduler()

        getter.add_callback("processor-a", mock.AsyncMock())
        getter.add_callback("processor-b", mock.AsyncMock())

        RefreshableGetter.remove_callbacks_for_tag("processor-a")

        assert getter.target in RefreshableGetter._target_to_data_caches
        assert len(getter.shared.callbacks) == 1
        assert getter.shared.callbacks[0]["tag"] == "processor-b"

    async def test_cancelled_cache_update_is_cleaned_up_after_completion(self):
        getter = HttpGetter(protocol="http", target="http://example.com/data")

        update_started = asyncio.Event()
        allow_update_to_finish = asyncio.Event()

        async def update_cache_once(_):
            update_started.set()
            await allow_update_to_finish.wait()
            return True

        with mock.patch.object(
            HttpGetter,
            "_update_cache_once",
            autospec=True,
            side_effect=update_cache_once,
        ):
            task = asyncio.create_task(getter._update_cache())

            await update_started.wait()

            update_task = getter.shared.update_task
            assert update_task is not None

            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert getter.shared.update_task is update_task

            allow_update_to_finish.set()
            await update_task
            await asyncio.sleep(0)

            assert getter.shared.update_task is None

    async def test_reset_does_not_recreate_target_during_running_refresh(self):
        getter = HttpGetter(protocol="http", target="http://example.com/data")
        shared = getter.shared
        shared.initialized = True
        shared.refresh_interval = 0
        shared.timeout_interval = 60

        update_started = asyncio.Event()
        allow_update_to_finish = asyncio.Event()

        async def get_from_target(_):
            update_started.set()
            await allow_update_to_finish.wait()
            return b"updated", "text/plain", True

        with mock.patch.object(
            HttpGetter,
            "_get_from_target",
            autospec=True,
            side_effect=get_from_target,
        ):
            refresh_task = asyncio.create_task(getter._refresh())

            await update_started.wait()

            RefreshableGetter.reset()

            assert getter.target not in RefreshableGetter._target_to_data_caches

            allow_update_to_finish.set()

            await refresh_task

            assert refresh_task.cancelled() is False
            assert getter.target not in RefreshableGetter._target_to_data_caches

    async def test_refresh_keeps_timed_out_target_while_update_is_running(self):
        getter = HttpGetter(protocol="http", target="http://example.com/data")
        shared = getter.shared

        shared.timeout_interval = 0
        shared.last_called = 0

        update_task = asyncio.create_task(asyncio.Event().wait())
        shared.update_task = update_task

        await RefreshableGetter.refresh()

        assert getter.target in RefreshableGetter._target_to_data_caches

        update_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await update_task

    async def test_concurrent_initialization_shares_single_config_load(self):
        first_getter = HttpGetter(
            protocol="http",
            target="http://example.com/data",
        )
        second_getter = HttpGetter(
            protocol="http",
            target="http://example.com/data",
        )

        config_load_started = asyncio.Event()
        allow_config_load_to_finish = asyncio.Event()
        config_load_count = 0

        async def get_getter_config_entry(_):
            nonlocal config_load_count
            config_load_count += 1
            config_load_started.set()
            await allow_config_load_to_finish.wait()

            return {
                "refresh_interval": 0,
                "timeout_interval": 60,
            }

        with mock.patch.object(
            HttpGetter,
            "_get_getter_config_entry",
            autospec=True,
            side_effect=get_getter_config_entry,
        ):
            first_task = asyncio.create_task(first_getter._ensure_initialized())

            await config_load_started.wait()

            second_task = asyncio.create_task(second_getter._ensure_initialized())
            await asyncio.sleep(0)

            assert config_load_count == 1

            allow_config_load_to_finish.set()

            await asyncio.gather(
                first_task,
                second_task,
            )

        assert first_getter.shared is second_getter.shared
        assert first_getter.shared.initialized is True

    async def test_reset_cancels_running_shared_initialization(self):
        getter = HttpGetter(
            protocol="http",
            target="http://example.com/data",
        )

        config_load_started = asyncio.Event()
        allow_config_load_to_finish = asyncio.Event()

        async def get_getter_config_entry(_):
            config_load_started.set()
            await allow_config_load_to_finish.wait()

            return {
                "refresh_interval": 0,
                "timeout_interval": 60,
            }

        with mock.patch.object(
            HttpGetter,
            "_get_getter_config_entry",
            autospec=True,
            side_effect=get_getter_config_entry,
        ):
            initialization = asyncio.create_task(getter._ensure_initialized())

            await config_load_started.wait()

            shared = getter.shared

            RefreshableGetter.reset()

            assert getter.target not in RefreshableGetter._target_to_data_caches

            with pytest.raises(asyncio.CancelledError):
                await initialization

            await asyncio.sleep(0)

            assert shared.initialization_task is None
            assert getter.target not in RefreshableGetter._target_to_data_caches

    async def test_uses_environment_settings_for_http_session(self, aiohttp_server):
        async def handler(_: web.Request) -> web.Response:
            return web.Response(
                text="content",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/data", handler)
        server = await aiohttp_server(app)

        getter = GetterFactory.from_string(str(server.make_url("/data")))

        client_session = aiohttp.ClientSession
        session_kwargs = []

        def create_session(*args, **kwargs):
            session_kwargs.append(kwargs)
            return client_session(*args, **kwargs)

        with mock.patch(
            "logprep.ng.util.getter.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            await getter.get()

        assert session_kwargs
        assert session_kwargs[0]["trust_env"] is True

    async def test_refresh_runs_target_schedulers_concurrently(self):
        first_getter = HttpGetter(
            protocol="http",
            target="http://example.com/first",
        )
        second_getter = HttpGetter(
            protocol="http",
            target="http://example.com/second",
        )

        first_started = asyncio.Event()
        second_started = asyncio.Event()
        allow_first_to_finish = asyncio.Event()

        async def run_first():
            first_started.set()
            await allow_first_to_finish.wait()

        async def run_second():
            second_started.set()

        first_scheduler = mock.Mock()
        first_scheduler.run_pending = mock.AsyncMock(side_effect=run_first)

        second_scheduler = mock.Mock()
        second_scheduler.run_pending = mock.AsyncMock(side_effect=run_second)

        first_getter.scheduler = first_scheduler
        second_getter.scheduler = second_scheduler

        refresh_task = asyncio.create_task(RefreshableGetter.refresh())

        await first_started.wait()
        await asyncio.sleep(0)

        try:
            assert second_started.is_set()
        finally:
            allow_first_to_finish.set()
            await refresh_task

        first_scheduler.run_pending.assert_awaited_once()
        second_scheduler.run_pending.assert_awaited_once()

    async def test_target_cleanup_does_not_cancel_global_refresh(self):
        getter = HttpGetter(
            protocol="http",
            target="http://example.com/data",
        )

        shared = getter.shared
        shared.initialized = True

        update_started = asyncio.Event()
        allow_update_to_finish = asyncio.Event()

        async def update_cache_once(_):
            update_started.set()
            await allow_update_to_finish.wait()
            return True

        scheduler = mock.Mock()
        scheduler.run_pending = mock.AsyncMock(side_effect=getter._refresh)
        shared.scheduler = scheduler

        with mock.patch.object(
            HttpGetter,
            "_update_cache_once",
            autospec=True,
            side_effect=update_cache_once,
        ):
            refresh_task = asyncio.create_task(RefreshableGetter.refresh())

            await update_started.wait()

            RefreshableGetter._discard_target(
                getter.target,
                shared,
            )

            await refresh_task

        assert getter.target not in RefreshableGetter._target_to_data_caches
