""" module for http connector """
from typing import List
from abc import ABC, abstractmethod
import queue
from fastapi import FastAPI, Request
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from logprep.abc.input import Input


app = FastAPI()


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    _messages: queue.Queue = queue.Queue()

    def __init__(self, messages: queue.Queue) -> None:
        self._messages = messages

    @abstractmethod
    async def _endpoint(self, **kwargs):
        """callback method for route"""
        ...

    @property
    @abstractmethod
    def _endpoint_path(self):
        """returns the path where you want to receive"""
        ...


class JSONHttpEndpoint(HttpEndpoint):
    """json endpoint http connector"""

    class Event(BaseModel):
        """model for event"""

        message: str

    async def _endpoint(self, event: Event):  # pylint: disable=arguments-differ
        """json endpoint method"""
        self._messages.put(event)

    @property
    def _endpoint_path(self):
        """json endpoint path"""
        return "/json"


class PlaintextHttpEndpoint(HttpEndpoint):
    """plaintext endpoint http connector"""

    async def _endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await request.body()
        self._messages.put({"message": data.decode("utf8")})

    @property
    def _endpoint_path(self):
        """plaintext endpoint path"""
        return "/plaintext"


class HttpConnector(Input):
    """
    Connector to accept log messages as http post requests
    """

    app: FastAPI = app

    _messages: queue.Queue = queue.Queue()

    _endpoints: List[HttpEndpoint] = [JSONHttpEndpoint, PlaintextHttpEndpoint]

    def __init__(self) -> None:

        self._endpoints = [endpoint(self._messages) for endpoint in self._endpoints]

        for endpoint in self._endpoints:
            self.app.add_api_route(
                path=f"{endpoint._endpoint_path}", endpoint=endpoint._endpoint, methods=["POST"]
            )

    def describe_endpoint(self):
        return f"{self.__class__.__name__}"

    def get_next(self, timeout: float):
        """returns the first message from the queue"""
        return self._messages.get(timeout=timeout)
