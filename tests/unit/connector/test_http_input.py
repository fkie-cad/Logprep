# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import requests
import uvicorn
import falcon
from logprep.connector.http.input import HttpConnector
from logprep.factory import Factory
from logprep.abc.input import FatalInputError
from tests.unit.connector.base import BaseInputTestCase


class TestHttpConnector(BaseInputTestCase):

    def setup_method(self):
        super().setup_method()
        self.object.pipeline_index = 1
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object.messages.empty():
            self.object.messages.get(timeout=0.001)
        self.target = self.object.target

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
        },
    }

    def teardown_method(self):
        self.object.shut_down()

    def test_create_connector(self):
        assert isinstance(self.object, HttpConnector)

    def test_has_falcon_asgi_app(self):
        assert isinstance(self.object.get_app_instance(), falcon.asgi.App)

    def test_no_pipeline_index(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        try:
            connector.setup()
            assert False
        except FatalInputError:
            assert True

    def test_not_first_pipeline(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector.pipeline_index = 2
        connector.setup()
        assert not hasattr(connector, "http_server")

    def test_get_error_code_on_get(self):
        resp = requests.get(url=f"{self.target}/json", timeout=0.5)
        assert resp.status_code == 405

    def test_get_error_code_too_many_requests(self):
        data = {"message": "my log message"}
        session = requests.Session()
        session.mount(
            "http://",
            requests.adapters.HTTPAdapter(pool_maxsize=20, max_retries=3, pool_block=True),
        )

        def get_url(url):
            for _ in range(100):
                _ = session.post(url, json=data)

        with ThreadPoolExecutor(max_workers=100) as executor:
            executor.submit(get_url, f"{self.target}/json")
        resp = requests.post(url=f"{self.target}/json", json=data, timeout=0.5)
        assert resp.status_code == 429

    def test_json_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/json", json=data, timeout=0.5)
        assert resp.status_code == 200

    def test_json_endpoint_match_wildcard_route(self):
        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/api/wildcard_path/json", json=data, timeout=0.5)
        assert resp.status_code == 200

    def test_json_endpoint_not_match_wildcard_route(self):
        data = {"message": "my log message"}
        resp = requests.post(
            url=f"{self.target}/api/wildcard_path/json/another_path", json=data, timeout=0.5
        )
        assert resp.status_code == 404

        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/json", json=data, timeout=0.5)
        assert resp.status_code == 200
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = requests.post(url=f"{self.target}/plaintext", json=data, timeout=0.5)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = requests.post(url=f"{self.target}/plaintext", data=data, timeout=0.5)
        assert resp.status_code == 200
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue.get("message") == data

    def test_jsonl_endpoint_match_regex_route(self):
        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/first/jsonl", json=data, timeout=0.5)
        assert resp.status_code == 200

    def test_jsonl_endpoint_not_match_regex_route(self):
        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/firs/jsonl", json=data, timeout=0.5)
        assert resp.status_code == 404

    def test_jsonl_endpoint_not_match_before_start_regex(self):
        data = {"message": "my log message"}
        resp = requests.post(url=f"{self.target}/api/first/jsonl", json=data, timeout=0.5)
        assert resp.status_code == 404

    def test_jsonl_endpoint_match_wildcard_regex_mix_route(self):
        data = {"message": "my log message"}
        resp = requests.post(
            url=f"{self.target}/third/jsonl/another_path/last_path", json=data, timeout=0.5
        )
        assert resp.status_code == 200

    def test_jsonl_endpoint_not_match_wildcard_regex_mix_route(self):
        data = {"message": "my log message"}
        resp = requests.post(
            url=f"{self.target}/api/third/jsonl/another_path", json=data, timeout=0.5
        )
        assert resp.status_code == 404

    def test_jsonl_messages_are_put_in_queue(self):
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        resp = requests.post(url=f"{self.target}/jsonl", data=data, timeout=0.5)
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
        requests.post(url=f"{self.target}/json", json=data, timeout=0.5)
        assert self.object.get_next(0.001) == (data, None)

    def test_get_next_returns_first_in_first_out(self):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            requests.post(url=self.target + "/json", json=message, timeout=0.5)
        assert self.object.get_next(0.001) == (data[0], None)
        assert self.object.get_next(0.001) == (data[1], None)
        assert self.object.get_next(0.001) == (data[2], None)

    def test_get_next_returns_first_in_first_out_for_mixed_endpoints(self):
        data = [
            {"endpoint": "json", "data": {"message": "first message"}},
            {"endpoint": "plaintext", "data": "second message"},
            {"endpoint": "json", "data": {"message": "third message"}},
        ]
        for message in data:
            endpoint, post_data = message.values()
            if endpoint == "json":
                requests.post(url=self.target + "/json", json=post_data, timeout=0.5)
            if endpoint == "plaintext":
                requests.post(url=self.target + "/plaintext", data=post_data, timeout=0.5)
        assert self.object.get_next(0.001)[0] == data[0].get("data")
        assert self.object.get_next(0.001)[0] == {"message": data[1].get("data")}
        assert self.object.get_next(0.001)[0] == data[2].get("data")

    def test_get_next_returns_none_for_empty_queue(self):
        assert self.object.get_next(0.001)[0] is None

    def test_server_returns_uvicorn_server_instance(self):
        assert isinstance(self.object.get_server_instance(), uvicorn.Server)

    def test_server_starts_threaded_server(self):
        message = {"message": "my message"}
        for i in range(100):
            message["message"] = f"message number {i}"
            requests.post(url=f"{self.target}/json", json=message, timeout=0.5)  # nosemgrep
        assert self.object.messages.qsize() == 100, "messages are put to queue"

    def test_get_metadata(self):
        message = {"message": "my message"}
        connector_config = deepcopy(self.CONFIG)
        connector_config["collect_meta"] = True
        connector_config["metafield_name"] = "custom"
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector.pipeline_index = 1
        connector.setup()
        target = connector.target
        resp = requests.post(url=f"{target}/json", json=message, timeout=0.5)  # nosemgrep
        assert resp.status_code == 200
        message = connector.messages.get(timeout=0.5)
        assert message["custom"]["url"] == target + "/json"
        assert message["custom"]["remote_addr"] == connector.host
        assert isinstance(message["custom"]["user_agent"], str)

    def test_server_multiple_config_changes(self):
        message = {"message": "my message"}
        connector_config = deepcopy(self.CONFIG)
        connector_config["uvicorn_config"]["port"] = 9001
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector.pipeline_index = 1
        connector.setup()
        target = connector.target
        resp = requests.post(url=f"{target}/json", json=message, timeout=0.5)  # nosemgrep
        assert resp.status_code == 200
        target = target.replace(":9001", ":9000")
        try:
            resp = requests.post(url=f"{target}/json", json=message, timeout=0.5)  # nosemgrep
        except requests.exceptions.ConnectionError as e:
            assert e.response is None
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector.pipeline_index = 1
        connector.setup()
        target = connector.target
        resp = requests.post(url=f"{target}/json", json=message, timeout=0.5)  # nosemgrep
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
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector.pipeline_index = 1
        connector.setup()
        test_event = "the content"
        requests.post(url=f"{self.target}/plaintext", data=test_event, timeout=0.5)  # nosemgrep

        expected_event = {
            "message": "the content",
            "Hmac": {
                "compressed_base64": "eJyrVs9NLS5OTE9Vt1JQL8lIVUjOzytJzStRrwUAem8JMA==",
                "hmac": "f0221a62c4ea38a4cc3af176faba010212e0ce7e0052c71fe726cbf3cb03dfd1",
            },
        }
        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"
