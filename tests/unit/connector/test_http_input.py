# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import json
import uvicorn
import requests
from fastapi.testclient import TestClient
from fastapi import FastAPI

from logprep.connector.http.input import HttpConnector
from tests.unit.connector.base import BaseInputTestCase


class TestHttpConnector(BaseInputTestCase):
    def setup_method(self):
        super().setup_method()
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        self.client = TestClient(self.object.app)

    CONFIG: dict = {"type": "http_input"}

    def test_create_connector(self):
        assert isinstance(self.object, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.object.app, FastAPI)

    def test_json_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json.dumps(data))
        assert resp.status_code == 200

    def test_json_message_is_put_in_queue(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json.dumps(data))
        assert resp.status_code == 200
        event_from_queue = self.object._messages.get(timeout=0.001)
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data=data)
        assert resp.status_code == 200
        event_from_queue = self.object._messages.get(timeout=0.001)
        assert event_from_queue.get("message") == data

    def test_get_next_returns_message_from_queue(self):
        data = {"message": "my log message"}
        self.client.post("/json", json.dumps(data))
        assert self.object.get_next(0.001) == (data, None)

    def test_get_next_returns_first_in_first_out(self):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            self.client.post("/json", json.dumps(message))
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
                self.client.post("/json", json.dumps(post_data))
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
        assert self.object._messages.qsize() == 100, "messages are put to queue"
