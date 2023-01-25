"""
HTTPInput
==========

A http input connector that spawns an uvicorn server and accepts http requests, parses them,
puts them to an internal queue and pops them via :code:`get_next` method.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      myhttpinput:
        type: http_input
        uvicorn_config:
            host: 0.0.0.0
            port: 9000
        endpoints:
            /firstendpoint: json
            /seccondendpoint: plaintext
            /thirdendpoint: jsonl
"""
import contextlib
import inspect
import json
import queue
import threading
from abc import ABC, abstractmethod
from typing import Mapping, Tuple, Union

import uvicorn
from attrs import define, field, validators
from fastapi import FastAPI, Request
from pydantic import BaseModel  # pylint: disable=no-name-in-module

from logprep.abc.input import Input

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    messages: queue.Queue

    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages

    @abstractmethod
    async def endpoint(self, **kwargs):
        """callback method for route"""
        ...  # pragma: no cover


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    class Event(BaseModel):
        """model for event"""

        message: str

    async def endpoint(self, event: Event):  # pylint: disable=arguments-differ
        """json endpoint method"""
        self.messages.put(dict(event))


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    async def endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        data = await request.body()
        data = data.decode("utf8")
        for line in data.splitlines():
            line = line.strip()
            if line:
                event = json.loads(line)
                self.messages.put(event)


class PlaintextHttpEndpoint(HttpEndpoint):
    """:code:`plaintext` endpoint to get the body from request and put it in :code:`message` field"""

    async def endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await request.body()
        self.messages.put({"message": data.decode("utf8")})


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
    """Connector to accept log messages as http post requests"""

    messages: queue.Queue = queue.Queue()

    _endpoint_registry: Mapping[str, HttpEndpoint] = {
        "json": JSONHttpEndpoint,
        "plaintext": PlaintextHttpEndpoint,
        "jsonl": JSONLHttpEndpoint,
    }

    @define(kw_only=True)
    class Config(Input.Config):
        """Config for HTTPInput"""

        uvicorn_config: Mapping[str, Union[str, int]] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(UVICORN_CONFIG_KEYS),
                    value_validator=lambda x, y, z: True,
                ),
            ]
        )
        """Configure uvicorn server. For possible settings see
        `uvicorn settings page <https://www.uvicorn.org/settings>`_.
        """
        endpoints: Mapping[str, str] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.matches_re(r"^\/.+"),
                    value_validator=validators.in_(["json", "plaintext", "jsonl"]),
                ),
            ]
        )
        """Configure endpoint routes with a Mapping of a path to an endpoint. Possible endpoints
        are: :code:`json`, :code:`jsonl`, :code:`plaintext`.
        
        .. autoclass:: logprep.connector.http.input.PlaintextHttpEndpoint
            :noindex:
        .. autoclass:: logprep.connector.http.input.JSONLHttpEndpoint
            :noindex:
        .. autoclass:: logprep.connector.http.input.JSONHttpEndpoint
            :noindex:
        """

    app: FastAPI
    server: uvicorn.Server

    __slots__ = ["app", "server"]

    def setup(self):
        super().setup()
        self.app = FastAPI()
        for endpoint_path, endpoint_name in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_name)
            endpoint = endpoint_class(self.messages)
            self.app.add_api_route(
                path=f"{endpoint_path}", endpoint=endpoint.endpoint, methods=["POST"]
            )
        uvicorn_config = uvicorn.Config(
            **self._config.uvicorn_config, app=self.app, log_level=self._logger.level
        )
        self.server = Server(uvicorn_config)

    def _get_event(self, timeout: float) -> Tuple:
        """returns the first message from the queue"""
        try:
            message = self.messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message
        except queue.Empty:
            return None, None
