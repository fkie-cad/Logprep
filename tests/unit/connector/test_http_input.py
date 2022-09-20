# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI

from logprep.connector.http.input import HttpConnector


class TestHttpConnector:
    def setup_method(self):
        self.connector = HttpConnector()
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
        event_from_queue = self.connector._messages.get()
        assert event_from_queue == data

    def test_plaintext_endpoint_accepts_post_request(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data)
        assert resp.status_code == 200

    def test_plaintext_message_is_put_in_queue(self):
        data = "my log message"
        resp = self.client.post("/plaintext", data=data)
        assert resp.status_code == 200
        event_from_queue = self.connector._messages.get()
        assert event_from_queue.get("message") == data
