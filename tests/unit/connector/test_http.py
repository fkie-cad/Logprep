# pylint: disable=missing-docstring
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from logprep.connector.http.connector import HttpConnector


class TestHttpConnector:
    def setup_method(self):
        self.connector = HttpConnector()
        self.client = TestClient(self.connector.app)

    def test_create_connector(self):
        assert isinstance(self.connector, HttpConnector)

    def test_has_fastapi_app(self):
        assert isinstance(self.connector.app, FastAPI)

    def test_accept_post_message(self):
        data = json.dumps({"message": "my test message"})
        resp = self.client.post("/event", data)
        assert resp.status_code == 200
