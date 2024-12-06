# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import gzip
import json
import multiprocessing
import queue
import random
import re
from copy import deepcopy
from unittest import mock

import pytest
import requests
import responses
from falcon import testing
from requests.auth import _basic_auth_str

from logprep.abc.input import FatalInputError
from logprep.connector.http.input import HttpInput
from logprep.factory import Factory
from logprep.framework.pipeline_manager import ThrottlingQueue
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE
from tests.unit.connector.base import BaseInputTestCase


@pytest.fixture(scope="function", name="credentials_file_path")
def create_credentials(tmp_path):
    secret_file_path = tmp_path / "secret-0.txt"
    secret_file_path.write_text("secret_password")
    credential_file_path = tmp_path / "credentials.yml"
    credential_file_path.write_text(
        f"""---
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
"""
    )

    return str(credential_file_path)


@mock.patch("logprep.connector.http.input.http.ThreadingHTTPServer", new=mock.MagicMock())
class TestHttpConnector(BaseInputTestCase):

    CONFIG: dict = {
        "type": "http_input",
        "message_backlog_size": 100,
        "collect_meta": False,
        "metafield_name": "@metadata",
        "uvicorn_config": {"port": 9000, "host": "127.0.0.1"},
        "endpoints": {
            "/json": "json",
            "/*json": "json",
            "/jsonl": "jsonl",
            "/(first|second)/jsonl": "jsonl",
            "/(third|fourth)/jsonl*": "jsonl",
            "/plaintext": "plaintext",
            "/auth-json-secret": "json",
            "/auth-json-file": "json",
            "/[A-Za-z0-9]*/[A-Z]{2}/json$": "json",
        },
    }

    expected_metrics = [
        *BaseInputTestCase.expected_metrics,
        "logprep_message_backlog_size",
        "logprep_number_of_http_requests",
    ]

    def setup_method(self):
        HttpInput.messages = ThrottlingQueue(
            ctx=multiprocessing.get_context(), maxsize=self.CONFIG.get("message_backlog_size")
        )
        super().setup_method()
        self.object.pipeline_index = 1
        with mock.patch(
            "logprep.connector.http.input.http.ThreadingHTTPServer", new=mock.MagicMock()
        ):
            self.object.setup()
        self.target = self.object.target
        self.client = testing.TestClient(self.object.app)

    def teardown_method(self):
        while not self.object.messages.empty():
            self.object.messages.get(timeout=0.001)
        self.object.shut_down()

    def test_create_connector(self):
        assert isinstance(self.object, HttpInput)

    def test_no_pipeline_index(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        try:
            connector.setup()
            assert False
        except FatalInputError:
            assert True

    def test_not_first_pipeline(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector.pipeline_index = 2
        connector.setup()
        assert connector.http_server is None

    def test_get_method_returns_200(self):
        resp = self.client.get("/json")
        assert resp.status_code == 200

    def test_get_method_returns_200_with_authentication(self):
        resp = self.client.get("/auth-json-secret")
        assert resp.status_code == 200

    def test_get_method_returns_429_if_queue_is_full(self):
        self.object.messages.full = mock.MagicMock()
        self.object.messages.full.return_value = True
        resp = self.client.get("/json")
        assert resp.status_code == 429

    def test_get_error_code_too_many_requests(self):
        data = {"message": "my log message"}
        self.object.messages.put = mock.MagicMock()
        self.object.messages.put.side_effect = queue.Full()
        resp = self.client.post("/json", json=data)
        assert resp.status_code == 429

    def test_json_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json=data)
        assert resp.status_code == 200

    def test_json_endpoint_match_wildcard_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json=data)
        assert resp.status_code == 200

    def test_json_endpoint_not_match_wildcard_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/api/wildcard_path/json/another_path", json=data)
        assert resp.status_code == 404

        data = {"message": "my log message"}
        resp = self.client.post("/json", json=data)
        assert resp.status_code == 200

        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = self.client.post("/plaintext", json=data)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = self.client.post("/plaintext", body=data)
        assert resp.status_code == 200
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue.get("message") == data

    def test_jsonl_endpoint_match_regex_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/first/jsonl", json=data)
        assert resp.status_code == 200

    def test_jsonl_endpoint_not_match_regex_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/firs/jsonl", json=data)
        assert resp.status_code == 404

    def test_jsonl_endpoint_not_match_before_start_regex(self):
        data = {"message": "my log message"}
        resp = self.client.post("/api/first/jsonl", json=data)
        assert resp.status_code == 404

    def test_jsonl_endpoint_match_wildcard_regex_mix_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/third/jsonl/another_path/last_path", json=data)
        assert resp.status_code == 200

    def test_jsonl_endpoint_not_match_wildcard_regex_mix_route(self):
        data = {"message": "my log message"}
        resp = self.client.post("/api/third/jsonl/another_path", json=data)
        assert resp.status_code == 404

    def test_jsonl_messages_are_put_in_queue(self):
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        resp = self.client.post("/jsonl", body=data)
        assert resp.status_code == 200
        assert self.object.messages.qsize() == 3
        event_from_queue = self.object.messages.get(timeout=1)
        assert event_from_queue["message"] == "my first log message"
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue["message"] == "my second log message"
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue["message"] == "my third log message"

    def test_get_next_returns_message_from_queue(self):
        data = {"message": "my log message"}
        self.client.post("/json", json=data)
        assert self.object.get_next(0.001) == data

    def test_get_next_returns_first_in_first_out(self):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            self.client.post("/json", json=message)
        assert self.object.get_next(0.001) == data[0]
        assert self.object.get_next(0.001) == data[1]
        assert self.object.get_next(0.001) == data[2]

    def test_get_next_returns_first_in_first_out_for_mixed_endpoints(self):
        data = [
            {"endpoint": "json", "data": {"message": "first message"}},
            {"endpoint": "plaintext", "data": "second message"},
            {"endpoint": "json", "data": {"message": "third message"}},
        ]
        for message in data:
            endpoint, post_data = message.values()
            if endpoint == "json":
                self.client.post("/json", json=post_data)
            if endpoint == "plaintext":
                self.client.post("/plaintext", body=post_data)
        assert self.object.get_next(0.001) == data[0].get("data")
        assert self.object.get_next(0.001) == {"message": data[1].get("data")}
        assert self.object.get_next(0.001) == data[2].get("data")

    def test_get_next_returns_none_for_empty_queue(self):
        assert self.object.get_next(0.001) is None

    def test_server_starts_threaded_server(self):
        message = {"message": "my message"}
        for i in range(90):
            message["message"] = f"message number {i}"
            self.client.post("/json", json=message)
        assert self.object.messages.qsize() == 90, "messages are put to queue"

    def test_get_metadata(self):
        message = {"message": "my message"}
        connector_config = deepcopy(self.CONFIG)
        connector_config["collect_meta"] = True
        connector_config["metafield_name"] = "custom"
        connector = Factory.create({"test connector": connector_config})
        connector.pipeline_index = 1
        connector.setup()
        client = testing.TestClient(connector.app)
        resp = client.post("/json", json=message)
        assert resp.status_code == 200
        message = connector.messages.get(timeout=0.5)
        assert message["custom"]["url"].endswith("/json")
        assert re.search(r"\d+\.\d+\.\d+\.\d+", message["custom"]["remote_addr"])
        assert isinstance(message["custom"]["user_agent"], str)

    def test_server_multiple_config_changes(self):
        message = {"message": "my message"}
        connector_config = deepcopy(self.CONFIG)
        connector_config["uvicorn_config"]["port"] = 9001
        connector = Factory.create({"test connector": connector_config})
        connector.pipeline_index = 1
        connector.setup()
        client = testing.TestClient(connector.app)
        resp = client.post("/json", json=message)
        assert resp.status_code == 200
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector.pipeline_index = 1
        connector.setup()
        resp = client.post("/json", json=message)
        assert resp.status_code == 200

    def test_get_next_with_hmac_of_raw_message(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
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
        connector = Factory.create({"test connector": connector_config})
        connector.pipeline_index = 1
        connector.setup()
        test_event = "the content"
        self.client.post("/plaintext", body=test_event)

        expected_event = {
            "message": "the content",
            "Hmac": {
                "compressed_base64": "eJyrVs9NLS5OTE9Vt1JQL8lIVUjOzytJzStRrwUAem8JMA==",
                "hmac": "f0221a62c4ea38a4cc3af176faba010212e0ce7e0052c71fe726cbf3cb03dfd1",
            },
        }
        connector_next_msg = connector.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"

    def test_endpoint_returns_401_if_authorization_not_provided(self, credentials_file_path):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = Factory.create({"test connector": self.CONFIG})
            new_connector.pipeline_index = 1
            new_connector.setup()
            client = testing.TestClient(new_connector.app)
            resp = client.post("/auth-json-file", body=json.dumps(data))
            assert resp.status_code == 401

    def test_endpoint_returns_401_on_wrong_authorization(self, credentials_file_path):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = Factory.create({"test connector": self.CONFIG})
            new_connector.pipeline_index = 1
            new_connector.setup()
            headers = {"Authorization": _basic_auth_str("wrong", "credentials")}
            client = testing.TestClient(new_connector.app, headers=headers)
            resp = client.post("/auth-json-file", body=json.dumps(data))
            assert resp.status_code == 401

    def test_endpoint_returns_200_on_correct_authorization_with_password_from_file(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = Factory.create({"test connector": self.CONFIG})
            new_connector.pipeline_index = 1
            new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "file_password")}
            client = testing.TestClient(new_connector.app, headers=headers)
            resp = client.post("/auth-json-file", body=json.dumps(data))
            assert resp.status_code == 200

    def test_endpoint_returns_200_on_correct_authorization_with_password_within_credentials_file(
        self, credentials_file_path
    ):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = Factory.create({"test connector": self.CONFIG})
            new_connector.pipeline_index = 1
            new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "secret_password")}
            client = testing.TestClient(new_connector.app, headers=headers)
            resp = client.post("/auth-json-secret", body=json.dumps(data))
            assert resp.status_code == 200

    def test_endpoint_returns_200_on_correct_authorization_for_subpath(self, credentials_file_path):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: credentials_file_path}
        data = {"message": "my log message"}
        with mock.patch.dict("os.environ", mock_env):
            new_connector = Factory.create({"test connector": self.CONFIG})
            new_connector.pipeline_index = 1
            new_connector.setup()
            headers = {"Authorization": _basic_auth_str("user", "password")}
            client = testing.TestClient(new_connector.app, headers=headers)
            resp = client.post("/auth-json-secret/AB/json", body=json.dumps(data))
            assert resp.status_code == 200

    def test_two_connector_instances_share_the_same_queue(self):
        new_connector = Factory.create({"test connector": self.CONFIG})
        assert self.object.messages is new_connector.messages

    def test_messages_is_multiprocessing_queue(self):
        assert isinstance(self.object.messages, multiprocessing.queues.Queue)

    def test_all_endpoints_share_the_same_queue(self):
        data = {"message": "my log message"}
        self.client.post("/json", json=data)
        assert self.object.messages.qsize() == 1
        data = "my log message"
        self.client.post("/plaintext", json=data)
        assert self.object.messages.qsize() == 2
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        self.client.post("/jsonl", body=data)
        assert self.object.messages.qsize() == 5

    def test_sets_target_to_https_schema_if_ssl_options(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config["uvicorn_config"]["ssl_keyfile"] = "path/to/keyfile"
        connector = Factory.create({"test connector": connector_config})
        assert connector.target.startswith("https://")

    def test_sets_target_to_http_schema_if_no_ssl_options(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        assert connector.target.startswith("http://")

    def test_get_event_sets_message_backlog_size_metric(self):
        self.object.metrics.message_backlog_size = 0
        random_number = random.randint(1, 100)
        for number in range(random_number):
            self.object.messages.put({"message": f"my message{number}"})
        self.object.get_next(0.001)
        assert self.object.metrics.message_backlog_size == random_number

    def test_enpoints_count_requests(self):
        self.object.metrics.number_of_http_requests = 0
        self.object.setup()
        random_number = random.randint(1, 100)
        for number in range(random_number):
            self.client.post("/json", json={"message": f"my message{number}"})
        assert self.object.metrics.number_of_http_requests == random_number

    @pytest.mark.parametrize("endpoint", ["json", "plaintext", "jsonl"])
    def test_endpoint_handles_gzip_compression(self, endpoint):
        data = {"message": "my log message"}
        data = gzip.compress(json.dumps(data).encode())
        headers = {"Content-Encoding": "gzip"}
        resp = self.client.post(f"/{endpoint}", body=data, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.parametrize("endpoint", ["json", "jsonl"])
    def test_raises_http_bad_request_on_decode_error(self, endpoint):
        data = "this is not a valid json nor jsonl"
        resp = self.client.post(f"/{endpoint}", body=data)
        assert resp.status_code == 400

    @responses.activate
    def test_health_endpoint_is_ready_if_all_endpoints_are_successful(self):
        for endpoint in self.object.health_endpoints:
            responses.get(f"http://127.0.0.1:9000{endpoint}", status=200)

        assert self.object.health(), "Health endpoint should be ready"

    @responses.activate
    def test_health_endpoint_is_not_ready_if_one_endpoint_has_status_429(self):
        for endpoint in self.object.health_endpoints[0:-2]:
            responses.get(f"http://127.0.0.1:9000{endpoint}", status=200)
        endpoint = self.object.health_endpoints[-1]
        responses.get(f"http://127.0.0.1:9000{endpoint}", status=429)  # bad
        assert not self.object.health(), "Health endpoint should not be ready"

    @responses.activate
    def test_health_endpoint_is_not_ready_if_one_endpoint_has_status_500(self):
        for endpoint in self.object.health_endpoints[1:-1]:
            responses.get(f"http://127.0.0.1:9000{endpoint}", status=200)
        endpoint = self.object.health_endpoints[0]
        responses.get(f"http://127.0.0.1:9000{endpoint}", status=500)  # bad
        assert not self.object.health(), "Health endpoint should not be ready"

    @responses.activate
    def test_health_endpoint_is_not_ready_on_connection_error(self):
        for endpoint in self.object.health_endpoints[1:-1]:
            responses.get(f"http://127.0.0.1:9000{endpoint}", status=200)
        endpoint = self.object.health_endpoints[0]
        responses.get(f"http://127.0.0.1:9000{endpoint}", body=requests.ConnectionError("bad"))
        assert not self.object.health(), "Health endpoint should not be ready"

    @responses.activate
    def test_health_endpoint_is_not_ready_if_one_endpoint_has_read_timeout(self):
        for endpoint in self.object.health_endpoints[1:-1]:
            responses.get(f"http://127.0.0.1:9000{endpoint}", status=200)
        endpoint = self.object.health_endpoints[0]
        responses.get(f"http://127.0.0.1:9000{endpoint}", body=requests.Timeout("bad"))
        assert not self.object.health(), "Health endpoint should not be ready"

    @responses.activate
    def test_health_check_logs_error(self):
        endpoint = self.object.health_endpoints[0]
        responses.get(f"http://127.0.0.1:9000{endpoint}", body=requests.Timeout("bad"))

        with mock.patch("logging.Logger.error") as mock_logger:
            assert not self.object.health(), "Health endpoint should not be ready"
            mock_logger.assert_called()

    @responses.activate
    def test_health_counts_errors(self):
        self.object.metrics.number_of_errors = 0
        endpoint = self.object.health_endpoints[0]
        responses.get(f"http://127.0.0.1:9000{endpoint}", status=500)  # bad
        assert not self.object.health()
        assert self.object.metrics.number_of_errors == 1

    def test_health_endpoints_are_shortened(self):
        config = deepcopy(self.CONFIG)
        endpoints = {
            "/json": "json",
            "/jsonl$": "jsonl",
            "/.*/blah$": "json",
            "/fooo.*/.+": "json",
            "/[A-Za-z0-9]*/[A-Z]{2}/json$": "json",
        }
        expected_matching_regexes = (
            "/json",
            "/jsonl$",
            "/b/blah$",
            "/fooob/b",
            "/[A-Za-z0-9]{5}/[A-Z]{2}/json$",
        )
        config["endpoints"] = endpoints
        connector = Factory.create({"test connector": config})
        health_endpoints = connector.health_endpoints
        for endpoint, expected in zip(health_endpoints, expected_matching_regexes):
            assert re.match(expected, endpoint)

    @pytest.mark.skip("Not implemented")
    def test_setup_calls_wait_for_health(self):
        pass
