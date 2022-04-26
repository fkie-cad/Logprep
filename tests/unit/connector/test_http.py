# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI

from logprep.connector.http.connector import (
    JSONHttpConnector,
    HttpConnector,
    PlaintextHttpConnector,
)


class TestJSONHttpConnector:
    def setup_method(self):
        self.connector = JSONHttpConnector()
        self.client = TestClient(self.connector.app)

    def test_create_connector(self):
        assert isinstance(self.connector, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.connector.app, FastAPI)

    def test_endpoint_accepts_post_request(self):
        data = {"message": "my log message"}
        endpoint_path = self.connector._endpoint_path
        resp = self.client.post(f"{endpoint_path}", json.dumps(data))
        assert resp.status_code == 200

    def test_json_message_is_put_in_queue(self):
        data = {"message": "my log message"}
        resp = self.client.post("/json", json.dumps(data))
        assert resp.status_code == 200
        event_from_queue = self.connector._messages.get()
        assert event_from_queue == data


class TestPlaintextHttpConnector:
    def setup_method(self):
        self.connector = PlaintextHttpConnector()
        self.client = TestClient(self.connector.app)

    def test_create_connector(self):
        assert isinstance(self.connector, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.connector.app, FastAPI)

    def test_endpoint_accepts_post_request(self):
        data = "my log message"
        endpoint_path = self.connector._endpoint_path
        resp = self.client.post(f"{endpoint_path}", data)
        assert resp.status_code == 200

    def test_json_message_is_put_in_queue(self):
        data = "my log message"
        headers = {"Content-type": "text/plain"}
        resp = self.client.post("/plaintext", data=data, headers=headers)
        assert resp.status_code == 200
        event_from_queue = self.connector._messages.get()
        assert event_from_queue.get("message") == data
