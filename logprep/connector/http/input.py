""" module for http connector """
import contextlib
import queue
import sys
import threading
from abc import ABC, abstractmethod
from typing import List, Mapping, Tuple

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from logprep.abc.input import Input

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


app = FastAPI()


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    _messages: queue.Queue

    def __init__(self, messages: queue.Queue) -> None:
        self._messages = messages

    @abstractmethod
    async def endpoint(self, **kwargs):
        """callback method for route"""
        ...

    @property
    @abstractmethod
    def endpoint_path(self):
        """returns the path where you want to receive"""
        ...


class JSONHttpEndpoint(HttpEndpoint):
    """json endpoint http connector"""

    class Event(BaseModel):
        """model for event"""

        message: str

    async def endpoint(self, event: Event):  # pylint: disable=arguments-differ
        """json endpoint method"""
        self._messages.put(dict(event))

    @property
    def endpoint_path(self):
        """json endpoint path"""
        return "/json"


class PlaintextHttpEndpoint(HttpEndpoint):
    """plaintext endpoint http connector"""

    async def endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await request.body()
        self._messages.put({"message": data.decode("utf8")})

    @property
    def endpoint_path(self):
        """plaintext endpoint path"""
        return "/plaintext"


class Server(uvicorn.Server):
    """the uvicorn server"""

    def install_signal_handlers(self):
        pass

    @contextlib.contextmanager
    def run_in_thread(self):
        """Context manager to run the server in a separate thread"""
        thread = threading.Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                pass
            yield
        finally:
            self.should_exit = True
            thread.join()


class HttpConnector(Input):
    """
    Connector to accept log messages as http post requests
    """

    app: FastAPI = app

    _messages: queue.Queue = queue.Queue()

    _endpoint_registry: Mapping[str, HttpEndpoint] = {
        "json": JSONHttpEndpoint,
        "plaintext": PlaintextHttpEndpoint,
    }

    endpoints: List[HttpEndpoint]

    @cached_property
    def server(self) -> uvicorn.Server:
        """returns the server instance"""
        config = uvicorn.Config(self.app, port=9000, log_level="info", workers=3)
        return Server(config)

    def setup(self):
        super().setup()

        endpoints = [
            endpoint(self._messages) for endpoint in list(self._endpoint_registry.values())
        ]
        for endpoint in endpoints:
            self.app.add_api_route(
                path=f"{endpoint.endpoint_path}", endpoint=endpoint.endpoint, methods=["POST"]
            )
        self.endpoints = endpoints

    def _get_event(self, timeout: float) -> Tuple:
        """returns the first message from the queue"""
        try:
            return self._messages.get(timeout=timeout), None
        except queue.Empty:
            return None, None
