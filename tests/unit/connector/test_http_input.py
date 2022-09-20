# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI

from logprep.connector.http.input import HttpConnector


class TestHttpConnector:
    def setup_method(self):
        self.connector = HttpConnector()
        self.connector.setup()
        # we have to empty the queue for testing
        while not self.connector._messages.empty():
            self.connector._messages.get(timeout=0.001)
        self.client = TestClient(self.connector.app)

    def test_create_connector(self):
        assert isinstance(self.connector, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.connector.app, FastAPI)

    def test_json_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json.dumps(data))
        assert resp.status_code == 200

    def test_json_message_is_put_in_queue(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json.dumps(data))
        assert resp.status_code == 200
        event_from_queue = self.connector._messages.get(timeout=0.001)
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data=data)
        assert resp.status_code == 200
        event_from_queue = self.connector._messages.get(timeout=0.001)
        assert event_from_queue.get("message") == data

    def test_get_next_returns_message_from_queue(self):
        data = {"message": "my log message"}
        self.client.post("/json", json.dumps(data))
        assert self.connector.get_next(0.001) == data

    def test_get_next_returns_first_in_first_out(self):
        data = [
            {"message": "first message"},
            {"message": "second message"},
            {"message": "third message"},
        ]
        for message in data:
            self.client.post("/json", json.dumps(message))
        assert self.connector.get_next(0.001) == data[0]
        assert self.connector.get_next(0.001) == data[1]
        assert self.connector.get_next(0.001) == data[2]

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
        assert self.connector.get_next(0.001) == data[0].get("data")
        assert self.connector.get_next(0.001) == {"message": data[1].get("data")}
        assert self.connector.get_next(0.001) == data[2].get("data")

    def test_get_next_returns_none_for_empty_queue(self):
        assert self.connector.get_next(0.001) is None
