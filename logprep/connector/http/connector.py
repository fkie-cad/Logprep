""" module for http connector """
from fastapi import FastAPI
from pydantic import BaseModel  # pylint: disable=no-name-in-module


class Event(BaseModel):
    message: str


class HttpConnector:
    """
    Connector to accept log messages as http post requests
    """

    app: FastAPI = FastAPI()

    def __init__(self) -> None:
        self.app.add_api_route(path="/event", endpoint=self.message, methods=["POST"])

    def message(self, event: Event):
        """index"""
        return {"status": "SUCCESS", "data": event}
