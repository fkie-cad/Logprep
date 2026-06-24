# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-public-methods

import asyncio
import gzip
import json
import queue
import random
import re
from contextlib import asynccontextmanager
from copy import deepcopy
from unittest import mock

import aiohttp
import pytest
from aiohttp import web
from falcon import testing
from requests.auth import _basic_auth_str

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.connector.http.input import HttpInput
from logprep.ng.util.worker.types import SizeLimitedQueue
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE
from tests.unit.ng.connector.base import BaseInputTestCase


@pytest.fixture(name="credentials_file_path")
def create_credentials(tmp_path):
    secret_file_path = tmp_path / "secret-0.txt"
    secret_file_path.write_text("secret_password")
    credential_file_path = tmp_path / "credentials.yml"
    credential_file_path.write_text(f"""---
input:
  endpoints:
    /auth-json-secret:
      username: user
      password_file: {secret_file_path}
    /auth-json-file:
      username: user
      password: file_password
    /.*/[A-Z]{{2}}/json$:
      username: user
      password: password
    /auth-json-two-creds:
      - username: user
        password: password
      - username: user2
        password_file: {secret_file_path}
""")

    return str(credential_file_path)


MODULE = HttpInput.__module__


@pytest.fixture
def health_server(aiohttp_server):
    @asynccontextmanager
    async def make_server(instance, endpoint_responses: dict[str, int | Exception]):
        async def handler(request: web.Request) -> web.Response:
            result = endpoint_responses.get(request.path, 200)
            if isinstance(result, Exception):
                raise result
            return web.Response(status=result)

        app = web.Application()
        app.router.add_get("/{path_info:.*}", handler)
        server = await aiohttp_server(app)
        with mock.patch.object(instance, "target", f"http://127.0.0.1:{server.port}"):
            yield server

    return make_server


class TestHttpConnector(BaseInputTestCase[HttpInput]):

    CONFIG: dict = {
        "type": "http_input",
        "message_backlog_size": 100,
        "collect_meta": False,
        "metafield_name": "@metadata",
        "uvicorn_config": {"port": 9000, "host": "127.0.0.1"},
        "endpoints": {
            "/json": "json",
            # TODO aiohttp has problems with this, why would you need to support /////json?
            # "/*json": "json",
            "/jsonl": "jsonl",
            "/(first|second)/jsonl": "jsonl",
            "/(third|fourth)/jsonl*": "jsonl",
            "/plaintext": "plaintext",
            "/auth-json-secret": "json",
            "/auth-json-file": "json",
            "/[A-Za-z0-9]*/[A-Z]{2}/json$": "json",
            "/auth-json-two-creds": "json",
        },
        "timeout": 0.1,
    }

    expected_metrics = [
        *BaseInputTestCase.expected_metrics,
        "logprep_message_backlog_size",
        "logprep_number_of_http_requests",
    ]

    @pytest.fixture(autouse=True)
    async def mock_create_and_run_server(self):
        with mock.patch(f"{MODULE}.{HttpInput.__name__}._create_and_run_server") as func:
            task = mock.AsyncMock()
            func.return_value = (mock.MagicMock(), task)
            yield func

    @pytest.fixture()
    async def asgi_app_from_setup(self, instance):
        await instance.setup()
        yield instance.app
        # TODO do we need the shutdown logic?
        while not instance.messages.empty():
            instance.messages.get_nowait()
        await instance.shut_down()

    @pytest.fixture
    async def client(self, asgi_app_from_setup):
        assert asgi_app_from_setup, "self.object needs to be initialized beforehand"
        async with testing.ASGIConductor(asgi_app_from_setup) as client:
            yield client

    def _create_log_event(self, data, original=None):
        return LogEvent(data, original=original, input_meta=InputMeta())

    async def test_create_connector(self, instance):
        assert isinstance(instance, HttpInput)

    async def test_get_method_returns_200(self, client):
        resp = await client.get("/json")
        assert resp.status_code == 200

    async def test_get_method_returns_200_with_authentication(self, client):
        resp = await client.get("/auth-json-secret")
        assert resp.status_code == 200

    async def test_get_method_returns_429_if_queue_is_full(self, instance, client):
        instance.messages.full = mock.MagicMock()
        instance.messages.full.return_value = True
        resp = await client.get("/json")
        assert resp.status_code == 429

    async def test_get_error_code_too_many_requests(self, instance, client):
        data = {"message": "my log message"}
        instance.messages.put = mock.MagicMock()
        instance.messages.put.side_effect = queue.Full()
        resp = await client.post("/json", json=data)
        assert resp.status_code == 429

    async def test_json_endpoint_accepts_post_request(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/json", json=data)
        assert resp.status_code == 200

    async def test_json_endpoint_match_wildcard_route(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/json", json=data)
        assert resp.status_code == 200

    async def test_json_endpoint_not_match_wildcard_route(self, instance, client):
        data = {"message": "my log message"}
        resp = await client.post("/api/wildcard_path/json/another_path", json=data)
        assert resp.status_code == 404

        data = {"message": "my log message"}
        resp = await client.post("/json", json=data)
        assert resp.status_code == 200

        event_from_queue = instance.messages.get_nowait()
        assert event_from_queue == data

    async def test_plaintext_endpoint_accepts_post_request(self, client):
        data = "my log message"
        resp = await client.post("/plaintext", json=data)
        assert resp.status_code == 200

    async def test_plaintext_message_is_put_in_queue(self, instance, client):
        data = "my log message"
        resp = await client.post("/plaintext", body=data)
        assert resp.status_code == 200
        event_from_queue = instance.messages.get_nowait()
        assert event_from_queue.get("message") == data

    async def test_jsonl_endpoint_match_regex_route(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/first/jsonl", json=data)
        assert resp.status_code == 200

    async def test_jsonl_endpoint_not_match_regex_route(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/firs/jsonl", json=data)
        assert resp.status_code == 404

    async def test_jsonl_endpoint_not_match_before_start_regex(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/api/first/jsonl", json=data)
        assert resp.status_code == 404

    async def test_jsonl_endpoint_match_wildcard_regex_mix_route(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/third/jsonl/another_path/last_path", json=data)
        assert resp.status_code == 200

    async def test_jsonl_endpoint_not_match_wildcard_regex_mix_route(self, client):
        data = {"message": "my log message"}
        resp = await client.post("/api/third/jsonl/another_path", json=data)
        assert resp.status_code == 404

    async def test_jsonl_messages_are_put_in_queue(self, instance, client):
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        resp = await client.post("/jsonl", body=data)
        assert resp.status_code == 200
        assert instance.messages.qsize() == 3
        event_from_queue = instance.messages.get_nowait()
        assert event_from_queue["message"] == "my first log message"
        event_from_queue = instance.messages.get_nowait()
        assert event_from_queue["message"] == "my second log message"
        event_from_queue = instance.messages.get_nowait()
        assert event_from_queue["message"] == "my third log message"

    async def test_get_next_returns_message_from_queue(self, instance, client):
        data = {"message": "my log message"}
        await client.post("/json", json=data)
        assert (await instance.get_next(0.001)).data == data

    async def test_get_next_returns_first_in_first_out(self, instance, client):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            await client.post("/json", json=message)
        assert (await instance.get_next(0.001)).data == data[0]
        assert (await instance.get_next(0.001)).data == data[1]
        assert (await instance.get_next(0.001)).data == data[2]

    async def test_get_next_returns_first_in_first_out_for_mixed_endpoints(self, instance, client):
        data = [
            {"endpoint": "json", "data": {"message": "first message"}},
            {"endpoint": "plaintext", "data": "second message"},
            {"endpoint": "json", "data": {"message": "third message"}},
        ]
        for message in data:
            endpoint, post_data = message.values()
            if endpoint == "json":
                await client.post("/json", json=post_data)
            if endpoint == "plaintext":
                await client.post("/plaintext", body=post_data)
        assert (await instance.get_next(0.001)).data == data[0].get("data")
        assert (await instance.get_next(0.001)).data == {"message": data[1].get("data")}
        assert (await instance.get_next(0.001)).data == data[2].get("data")

    async def test_get_next_returns_none_for_empty_queue(self, instance):
        assert (await instance.get_next(0.001)) is None

    async def test_server_starts_threaded_server(self, instance, client):
        message = {"message": "my message"}
        for i in range(90):
            message["message"] = f"message number {i}"
            await client.post("/json", json=message)
        assert instance.messages.qsize() == 90, "messages are put to queue"

    async def test_get_metadata(
        self,
    ):
        message = {"message": "my message"}
        connector_config = deepcopy(self.CONFIG)
        connector_config["collect_meta"] = True
        connector_config["metafield_name"] = "custom"
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.AsyncMock()
        await connector.setup()
        async with testing.ASGIConductor(connector.app) as client:
            resp = await client.post("/json", json=message)
            assert resp.status_code == 200
            message = connector.messages.get_nowait()
            assert message["custom"]["url"].endswith("/json")
            assert re.search(r"\d+\.\d+\.\d+\.\d+", message["custom"]["remote_addr"])
            assert isinstance(message["custom"]["user_agent"], str)

    async def test_original_event_field_with_event_as_dict(self):
        message = {"message": "my message"}
        connector = self._create_test_instance(
            {"original_event_field": {"target_field": "event.original", "format": "dict"}}
        )

        await connector.setup()
        async with testing.ASGIConductor(connector.app) as client:
            resp = await client.post("/json", json=message)
            assert resp.status_code == 200
            message = connector.messages.get_nowait()
            expected = {"event": {"original": {"message": "my message"}}}
            assert message == expected, f"{expected} does not equal {message}"

    async def test_original_event_field_with_preprocessor_active_raises_invalid_configuration_error(
        self,
    ):
        with pytest.raises(InvalidConfigurationError):
            self._create_test_instance(
                {
                    "original_event_field": {"target_field": "event.original", "format": "dict"},
                    "preprocessing": {
                        "add_full_event_to_target_field": {
                            "target_field": "event.original",
                            "format": "str",
                        }
                    },
                }
            )

    async def test_original_event_field_with_event_as_string(self, client):
        message = {"message": "my message"}
        instance = self._create_test_instance(
            {"original_event_field": {"target_field": "event.original", "format": "str"}}
        )
        await instance.setup()
        async with testing.ASGIConductor(instance.app) as client:
            resp = await client.post("/json", json=message)
            assert resp.status_code == 200
            message = instance.messages.get_nowait()
            expected = {"event": {"original": '{"message": "my message"}'}}
            assert message == expected, f"{expected} does not equal {message}"

    async def test_server_multiple_config_changes(self, client):
        message = {"message": "my message"}
        instance = self._create_test_instance(
            {"uvicorn_config": {**self.CONFIG["uvicorn_config"], "port": 9091}}
        )
        await instance.setup()
        async with testing.ASGIConductor(instance.app) as client:
            resp = await client.post("/json", json=message)
            assert resp.status_code == 200
            instance = self._create_test_instance()
            await instance.setup()
            resp = await client.post("/json", json=message)
            assert resp.status_code == 200

    async def test_get_next_with_hmac_of_raw_message(self):
        instance = self._create_test_instance(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        await instance.setup()
        test_event = "the content"
        async with testing.ASGIConductor(instance.app) as client:
            await client.post("/plaintext", body=test_event)

        expected_event = LogEvent(
            data={
                "message": "the content",
                "Hmac": {
                    "compressed_base64": "eJyrVs9NLS5OTE9Vt1JQL8lIVUjOzytJzStRrwUAem8JMA==",
                    "hmac": "f0221a62c4ea38a4cc3af176faba010212e0ce7e0052c71fe726cbf3cb03dfd1",
                },
            },
            original=b"{'message': 'the content'}",
            input_meta=InputMeta(),
        )
        connector_next_msg = await instance.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"

    async def test_endpoint_returns_401_if_authorization_not_provided(self, credentials_file_path):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()
            async with testing.ASGIConductor(new_connector.app) as client:
                resp = await client.post("/auth-json-file", body=json.dumps(data))
                assert resp.status_code == 401

    async def test_endpoint_returns_401_on_wrong_authorization(self, credentials_file_path):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()
            headers = {"Authorization": _basic_auth_str("wrong", "credentials")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-file", body=json.dumps(data))
                assert resp.status_code == 401

    async def test_endpoint_returns_200_on_correct_authorization_with_password_from_file(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "file_password")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-file", body=json.dumps(data))
                assert resp.status_code == 200

    async def test_endpoint_returns_200_on_correct_authorization_for_subpath_and_both_credentials(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()

            headers = {"Authorization": _basic_auth_str("user2", "secret_password")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-two-creds", body=json.dumps(data))
                assert resp.status_code == 200

            headers = {"Authorization": _basic_auth_str("user", "password")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-two-creds", body=json.dumps(data))
                assert resp.status_code == 200

    async def test_endpoint_returns_401_on_wrong_authorization_with_second_credential(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()

            headers = {"Authorization": _basic_auth_str("wrong", "credentials")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-two-creds", body=json.dumps(data))
                assert resp.status_code == 401

    async def test_endpoint_returns_200_on_correct_authorization_with_password_within_credentials_file(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "secret_password")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-secret", body=json.dumps(data))
                assert resp.status_code == 200

    async def test_endpoint_returns_200_on_correct_authorization_for_subpath(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = self._create_test_instance()
            await new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "password")}
            async with testing.ASGIConductor(new_connector.app, headers=headers) as client:
                resp = await client.post("/auth-json-secret/AB/json", body=json.dumps(data))
                assert resp.status_code == 200

    async def test_messages_is_size_limited_queue(self, instance):
        assert isinstance(instance.messages, SizeLimitedQueue)

    async def test_all_endpoints_share_the_same_queue(self, instance, client):
        data = {"message": "my log message"}
        await client.post("/json", json=data)
        assert instance.messages.qsize() == 1
        data = "my log message"
        await client.post("/plaintext", json=data)
        assert instance.messages.qsize() == 2
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        await client.post("/jsonl", body=data)
        assert instance.messages.qsize() == 5

    async def test_sets_target_to_https_schema_if_ssl_options(self):
        instance = self._create_test_instance(
            {"uvicorn_config": {**self.CONFIG["uvicorn_config"], "ssl_keyfile": "path/to/keyfile"}}
        )
        assert instance.target.startswith("https://")

    async def test_sets_target_to_http_schema_if_no_ssl_options(self):
        instance = self._create_test_instance()
        assert instance.target.startswith("http://")

    async def test_get_event_sets_message_backlog_size_metric(self, instance):
        instance.metrics.message_backlog_size = 0
        random_number = random.randint(1, 100)
        for number in range(random_number):
            instance.messages.put_nowait({"message": f"my message{number}"})
        await instance.get_next(0.001)
        assert instance.metrics.message_backlog_size == random_number

    async def test_endpoints_count_requests(self, instance, client):
        instance.metrics.number_of_http_requests = 0
        await instance.setup()
        random_number = random.randint(1, 100)
        for number in range(random_number):
            await client.post("/json", json={"message": f"my message{number}"})
        assert instance.metrics.number_of_http_requests == random_number

    @pytest.mark.parametrize("endpoint", ["json", "plaintext", "jsonl"])
    async def test_endpoint_handles_gzip_compression(self, endpoint, client):
        data = {"message": "my log message"}
        data = gzip.compress(json.dumps(data).encode())
        headers = {"Content-Encoding": "gzip"}
        resp = await client.post(f"/{endpoint}", body=data, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.parametrize("endpoint", ["json", "jsonl"])
    async def test_raises_http_bad_request_on_decode_error(self, endpoint, client):
        data = "this is not a valid json nor jsonl"
        resp = await client.post(f"/{endpoint}", body=data)
        assert resp.status_code == 400

    async def test_health_endpoints_are_gettable(self, instance, client):
        for endpoint in instance.health_endpoints:
            resp = await client.get(endpoint)
            assert resp.status_code == 200, f"could not get {endpoint}"

    async def test_positive_health_check_if_all_endpoints_are_successful(
        self, instance: HttpInput, health_server
    ):
        responses = {ep: 200 for ep in instance.health_endpoints}
        async with health_server(instance, responses):
            assert await instance.health()

    @pytest.mark.parametrize(
        "failed_endpoint_index",
        [pytest.param(i, id=pattern) for i, pattern in enumerate(CONFIG["endpoints"].keys())],
    )
    async def test_health_endpoint_is_not_ready_if_one_endpoint_has_status_429(
        self, instance: HttpInput, failed_endpoint_index, health_server
    ):
        responses = {
            ep: (429 if failed_endpoint_index == i else 200)
            for i, ep in enumerate(instance.health_endpoints)
        }
        async with health_server(instance, responses):
            assert not await instance.health(), "Health endpoint should not be ready"

    @pytest.mark.parametrize(
        "failed_endpoint_index",
        [pytest.param(i, id=pattern) for i, pattern in enumerate(CONFIG["endpoints"].keys())],
    )
    async def test_health_endpoint_is_not_ready_if_one_endpoint_has_status_500(
        self, instance: HttpInput, failed_endpoint_index, health_server
    ):
        responses = {
            ep: (500 if failed_endpoint_index == i else 200)
            for i, ep in enumerate(instance.health_endpoints)
        }
        async with health_server(instance, responses):
            assert not await instance.health(), "Health endpoint should not be ready"

    @pytest.mark.parametrize(
        "failed_endpoint_index",
        [pytest.param(i, id=pattern) for i, pattern in enumerate(CONFIG["endpoints"].keys())],
    )
    async def test_health_endpoint_is_not_ready_on_connection_error(
        self, instance: HttpInput, failed_endpoint_index, health_server
    ):
        responses = {
            ep: (aiohttp.ClientError("did not work") if i == failed_endpoint_index else 200)
            for i, ep in enumerate(instance.health_endpoints)
        }
        async with health_server(instance, responses):
            assert not await instance.health(), "Health endpoint should not be ready"

    @pytest.mark.parametrize(
        "failed_endpoint_index",
        [pytest.param(i, id=pattern) for i, pattern in enumerate(CONFIG["endpoints"].keys())],
    )
    async def test_health_endpoint_is_not_ready_if_one_endpoint_has_read_timeout(
        self, instance: HttpInput, failed_endpoint_index, health_server
    ):
        responses = {
            ep: (asyncio.TimeoutError() if i == failed_endpoint_index else 200)
            for i, ep in enumerate(instance.health_endpoints)
        }
        async with health_server(instance, responses):
            assert not await instance.health(), "Health endpoint should not be ready"

    @pytest.mark.parametrize(
        "failed_endpoint_index",
        [pytest.param(i, id=pattern) for i, pattern in enumerate(CONFIG["endpoints"].keys())],
    )
    async def test_health_check_logs_error(self, instance, failed_endpoint_index, health_server):
        endpoint = instance.health_endpoints[failed_endpoint_index]
        responses = {
            ep: (asyncio.TimeoutError() if ep == endpoint else 200)
            for ep in instance.health_endpoints
        }
        async with health_server(instance, responses):
            with mock.patch("logging.Logger.error") as mock_logger:
                assert not await instance.health(), "Health endpoint should not be ready"
                mock_logger.assert_called()

    async def test_health_counts_errors(self, instance, health_server):
        instance.metrics.number_of_errors = 0
        responses = {instance.health_endpoints[0]: 500}
        async with health_server(instance, responses):
            assert not await instance.health()
        assert instance.metrics.number_of_errors == 1

    async def test_health_endpoints_are_shortened(self):
        expected_matching_regexes = (
            "/json",
            "/jsonl$",
            "/b/blah$",
            "/fooob/b",
            "/[A-Za-z0-9]{5}/[A-Z]{2}/json$",
        )
        instance = self._create_test_instance(
            {
                "endpoints": {
                    "/json": "json",
                    "/jsonl$": "jsonl",
                    "/.*/blah$": "json",
                    "/fooo.*/.+": "json",
                    "/[A-Za-z0-9]*/[A-Z]{2}/json$": "json",
                }
            }
        )
        health_endpoints = instance.health_endpoints
        for endpoint, expected in zip(health_endpoints, expected_matching_regexes):
            assert re.match(expected, endpoint)

    @pytest.mark.skip("Not implemented")
    async def test_setup_calls_wait_for_health(self):
        pass

    async def test_http_input_iterator(self, instance, client):
        batch_data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in batch_data:
            await client.post("/json", json=message)

        assert (await anext(instance)).data == {"message": "first message"}
        assert (await anext(instance)).data == {"message": "second message"}
        assert (await anext(instance)).data == {"message": "third message"}
        assert (await anext(instance)) is None  # sensitive to config.timeout
