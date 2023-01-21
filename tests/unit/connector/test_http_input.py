# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
import json

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from logprep.connector.http.input import HttpConnector
from logprep.factory import Factory
from tests.unit.connector.base import BaseInputTestCase


class TestHttpConnector(BaseInputTestCase):
    def setup_method(self):
        super().setup_method()
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object.messages.empty():
            self.object.messages.get(timeout=0.001)
        self.client = TestClient(self.object.app)

    CONFIG: dict = {
        "type": "http_input",
        "uvicorn_config": {"port": 9000, "host": "127.0.0.1"},
        "endpoints": {"/json": "json", "/jsonl": "jsonl", "/plaintext": "plaintext"},
    }

    def test_create_connector(self):
        assert isinstance(self.object, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.object.app, FastAPI)

    def test_json_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        resp = self.client.post(url="/json", data=json.dumps(data))
        assert resp.status_code == 200

    def test_json_message_is_put_in_queue(self):
        data = {"message": "my log message"}
        resp = self.client.post(url="/json", data=json.dumps(data))
        assert resp.status_code == 200
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = self.client.post(url="/plaintext", data=data)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data=data)
        assert resp.status_code == 200
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue.get("message") == data

    def test_jsonl_messages_are_put_in_queue(self):
        data = """
        {"message": "my first log message"}
        {"message": "my second log message"}
        {"message": "my third log message"}
        """
        resp = self.client.post("/jsonl", data=data)
        assert resp.status_code == 200
        assert self.object.messages.qsize() == 3
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == {"message": "my first log message"}
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == {"message": "my second log message"}
        event_from_queue = self.object.messages.get(timeout=0.001)
        assert event_from_queue == {"message": "my third log message"}

    def test_get_next_returns_message_from_queue(self):
        data = {"message": "my log message"}
        self.client.post(url="/json", data=json.dumps(data))
        assert self.object.get_next(0.001) == (data, None)

    def test_get_next_returns_first_in_first_out(self):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            self.client.post(url="/json", data=json.dumps(message))
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
                self.client.post(url="/json", data=json.dumps(post_data))
            if endpoint == "plaintext":
                self.client.post("/plaintext", data=post_data)
        assert self.object.get_next(0.001)[0] == data[0].get("data")
        assert self.object.get_next(0.001)[0] == {"message": data[1].get("data")}
        assert self.object.get_next(0.001)[0] == data[2].get("data")

    def test_get_next_returns_none_for_empty_queue(self):
        assert self.object.get_next(0.001)[0] is None

    def test_server_returns_uvicorn_server_instance(self):
        assert isinstance(self.object.server, uvicorn.Server)

    def test_server_starts_threaded_server_with_context_manager(self):
        with self.object.server.run_in_thread():
            message = {"message": "my message"}
            for i in range(100):
                message["message"] = f"message number {i}"
                requests.post(url="http://127.0.0.1:9000/json", json=message)  # nosemgrep
        assert self.object.messages.qsize() == 100, "messages are put to queue"

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
        connector.setup()
        test_event = "the content"
        with connector.server.run_in_thread():
            requests.post(url="http://127.0.0.1:9000/plaintext", data=test_event)  # nosemgrep

        expected_event = {
            "message": "the content",
            "Hmac": {
                "compressed_base64": "eJyrVs9NLS5OTE9Vt1JQL8lIVUjOzytJzStRrwUAem8JMA==",
                "hmac": "f0221a62c4ea38a4cc3af176faba010212e0ce7e0052c71fe726cbf3cb03dfd1",
            },
        }
        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"
