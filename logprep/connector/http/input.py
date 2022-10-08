"""
HTTPInput
==========

A http input connector that spawns an uvicorn server and accepts http requests, parses them,
put them to an internal queue and pops them via get_next method.

This Processor is not supported for python 3.6 and lower versions.

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
import json
import inspect
import queue
import sys
import threading
from abc import ABC, abstractmethod
from typing import Mapping, Tuple, Union

import uvicorn
from attrs import define, field, validators
from fastapi import FastAPI, Request
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from logprep.abc.input import Input

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property
uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    _messages: queue.Queue

    def __init__(self, messages: queue.Queue) -> None:
        self._messages = messages

    @abstractmethod
    async def endpoint(self, **kwargs):
        """callback method for route"""
        ...


class JSONHttpEndpoint(HttpEndpoint):
    """json endpoint http connector"""

    class Event(BaseModel):
        """model for event"""

        message: str

    async def endpoint(self, event: Event):  # pylint: disable=arguments-differ
        """json endpoint method"""
        self._messages.put(dict(event))


class JSONLHttpEndpoint(HttpEndpoint):
    """json endpoint http connector"""

    async def endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        data = await request.body()
        data = data.decode("utf8")
        for line in data.splitlines():
            line = line.strip()
            if line:
                event = json.loads(line)
                self._messages.put(event)


class PlaintextHttpEndpoint(HttpEndpoint):
    """plaintext endpoint http connector"""

    async def endpoint(self, request: Request):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await request.body()
        self._messages.put({"message": data.decode("utf8")})


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

    _messages: queue.Queue = queue.Queue()

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
        """Configure uvicorn server. For possible settings see `uvicorn settings page`_
        
        .. _uvicorn settings page: https://www.uvicorn.org/settings
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
        """Configure endpoint routes with a Mapping of an path to an endpoint. Possible endpoints
        are: :code:`json`, :code:`jsonl`, :code:`plaintext`
        """

    app: FastAPI
    server: uvicorn.Server

    __slots__ = ["app", "server"]

    def setup(self):
        super().setup()
        self.app = FastAPI()
        for endpoint_path, endpoint_name in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_name)
            endpoint = endpoint_class(self._messages)
            self.app.add_api_route(
                path=f"{endpoint_path}", endpoint=endpoint.endpoint, methods=["POST"]
            )
        config = uvicorn.Config(
            **self._config.uvicorn_config, app=self.app, log_level=self._logger.level
        )
        self.server = Server(config)

    def _get_event(self, timeout: float) -> Tuple:
        """returns the first message from the queue"""
        try:
            return self._messages.get(timeout=timeout), None
        except queue.Empty:
            return None, None
