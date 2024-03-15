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
import queue
import threading
from abc import ABC
from logging import Logger, getLogger
import logging
import re
from typing import Mapping, Tuple, Union
import msgspec
import uvicorn
from attrs import define, field, validators
import falcon.asgi

from logprep.abc.input import Input
from logprep.util import defaults

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    messages: queue.Queue

    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder = msgspec.json.Decoder()

    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """json endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        self.messages.put(self._decoder.decode(data))


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    _decoder = msgspec.json.Decoder()

    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        for line in data.splitlines():
            line = line.strip()
            if line:
                event = self._decoder.decode(line)
                self.messages.put(event)


class PlaintextHttpEndpoint(HttpEndpoint):
    """:code:`plaintext` endpoint to get the body from request
    and put it in :code:`message` field"""

    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await req.stream.read()
        self.messages.put({"message": data.decode("utf8")})


class Server(uvicorn.Server):
    """the uvicorn server"""

    def install_signal_handlers(self):
        pass

    def override_runtime_logging(self):
        """uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        logging.getLogger("uvicorn").removeHandler(logging.getLogger("uvicorn").handlers[0])
        logging.getLogger("uvicorn").addHandler(logging.getLogger("Logprep").parent.handlers[0])
        http_server_name = logging.getLogger("Logprep").name + " HTTPServer"
        logging.getLogger("uvicorn.error").name = http_server_name
        logging.getLogger("uvicorn.access").name = http_server_name

    # https://github.com/encode/uvicorn/issues/742#issuecomment-674411676
    @contextlib.contextmanager
    def run_in_thread(self):
        """Context manager to run the server in a separate thread"""

        thread = threading.Thread(target=self.run)
        thread.start()
        self.override_runtime_logging()
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

    __slots__ = []

    def __init__(self, name: str, configuration: "HttpConnector.Config", logger: Logger) -> None:
        super().__init__(name, configuration, logger)

    def setup(self):
        super().setup()
        self.app = falcon.asgi.App()

        for endpoint_path, endpoint_name in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_name)
            endpoint = endpoint_class(self.messages)
            self.app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))

        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        uvicorn_config = uvicorn.Config(
            **self._config.uvicorn_config,
            app=self.app,
            log_level=self._logger.level,
            log_config=log_config,
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


def route_compile_helper(input_re_str: str):
    """falcon add_sink handles prefix routes as independent URI elements
    therefore we need regex position anchors to ensure beginning and
    end of given route and replace * with .* for user-friendliness
    """
    input_re_str = input_re_str.replace("*", ".*")
    input_re_str = "^" + input_re_str + "$"
    return re.compile(input_re_str)
