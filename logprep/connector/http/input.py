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

import json
import inspect
import signal
import queue
import threading
from abc import ABC
from logging import Logger
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

# Config Parts that's checked for Config Change
HTTP_INPUT_CONFIG_KEYS = ["preprocessing", "uvicorn_config", "endpoints"]


def has_config_changed(
    old_config: Input.Config, new_config: Input.Config, check_attrs=None
) -> bool:
    """Compare Input Connector Configs for specific areas
    specified in check_attrs
    For sake of simplicity JSON Strings are compared instead
    of compare nested dict key-values
    """

    old_config_dict = {}
    new_config_dict = {}
    for key in check_attrs:
        old_config_dict.update(getattr(old_config, key))
        new_config_dict.update(getattr(new_config, key))
    cur_json = json.dumps(old_config_dict, sort_keys=True)
    new_json = json.dumps(new_config_dict, sort_keys=True)

    if cur_json == new_json:
        return False
    return True


def route_compile_helper(input_re_str: str):
    """falcon add_sink handles prefix routes as independent URI elements
    therefore we need regex position anchors to ensure beginning and
    end of given route and replace * with .* for user-friendliness
    """
    input_re_str = input_re_str.replace("*", ".*")
    input_re_str = "^" + input_re_str + "$"
    return re.compile(input_re_str)


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


class ThreadingHTTPServer(threading.Thread):
    """Threading Wrapper around Uvicorn Server"""

    def __init__(
        self,
        connector_config,
        endpoints_config: dict,
        log_level: str,
    ) -> None:
        super().__init__()
        self.connector_config = connector_config
        self.endpoints_config = endpoints_config
        self.uvicorn_config = self.connector_config.uvicorn_config
        self.init_web_application_server(self.endpoints_config)
        log_config = self.init_log_config()
        self.compiled_config = uvicorn.Config(
            **self.uvicorn_config,
            app=self.app,
            log_level=log_level,
            log_config=log_config,
        )
        self.server = uvicorn.Server(self.compiled_config)
        self.override_runtime_logging()
        self.start()
        while not self.server.started:
            pass

    def init_log_config(self) -> dict:
        """use for uvicorn same log formatter like for logprep"""
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT

        return log_config

    def init_web_application_server(self, endpoints_config: dict) -> None:
        "init application server"
        self.app = falcon.asgi.App()
        for endpoint_path, endpoint in endpoints_config.items():
            self.app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))

    def override_runtime_logging(self):
        """uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        logging.getLogger("uvicorn").removeHandler(logging.getLogger("uvicorn").handlers[0])
        logging.getLogger("uvicorn").addHandler(logging.getLogger("Logprep").parent.handlers[0])
        http_server_name = logging.getLogger("Logprep").name + " HTTPServer"
        logging.getLogger("uvicorn.error").name = http_server_name
        logging.getLogger("uvicorn.access").name = http_server_name

    def run(self):
        """Context manager to run the server in a separate thread"""
        self.server.run()
        while not self.server.should_exit:
            pass

    def shut_down(self):
        """Gracefully exit uvicorn server"""
        self.server.should_exit = True
        self.server.handle_exit(signal.SIGINT, frame=None)


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
                    # lamba xyz tuple necessary because of input structure
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
        internal_uvicorn_config = {
            "lifespan": "off",
            "loop": "asyncio",
            "timeout_graceful_shutdown": 0,
        }
        self._config.uvicorn_config.update(internal_uvicorn_config)
        self.logger = logger
        self.port = self._config.uvicorn_config["port"]
        self.host = self._config.uvicorn_config["host"]
        self.target = "http://" + self.host + ":" + str(self.port)
        self.sthread = None

    def setup(self):
        super().setup()

        start_server = False
        http_thread_exists, http_thread = check_http_thread()
        if http_thread_exists:
            config_update = has_config_changed(
                http_thread.connector_config, self._config, check_attrs=HTTP_INPUT_CONFIG_KEYS
            )
            if config_update:
                self.shut_down()
                self.logger.info("HTTP Input Connector Config changed. Restart Uvicorn Server.")
                start_server = True
            else:
                self.logger.info(
                    "HTTP Input Connector Config didn't change. Remain running Uvicorn Server."
                )
        else:
            start_server = True

        if start_server:
            endpoints_config = {}
            for endpoint_path, endpoint_name in self._config.endpoints.items():
                endpoint_class = self._endpoint_registry.get(endpoint_name)
                endpoints_config[endpoint_path] = endpoint_class(self.messages)

            self.sthread = ThreadingHTTPServer(
                connector_config=self._config,
                endpoints_config=endpoints_config,
                log_level=self._logger.level,
            )

    def _get_event(self, timeout: float) -> Tuple:
        """returns the first message from the queue"""
        try:
            message = self.messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message
        except queue.Empty:
            return None, None

    def get_app_instance(self):
        """Return app instance from webserver thread"""
        return self.sthread.app

    def get_server_instance(self):
        """Return server instance from webserver thread"""
        return self.sthread.server

    def shut_down(self):
        """Raises HTTP Server internal stop flag and waits to join
        We need to look for the thread this way as newly initiated http
        server instances doesn't share relation to the original http server
        that is created with the first HTTP Connector Object
        """
        http_thread_exists, http_thread = check_http_thread()
        if http_thread_exists:
            http_thread.shut_down()
            http_thread.join()


def check_http_thread(compare_class=ThreadingHTTPServer) -> (bool, ThreadingHTTPServer):
    """enumerate running threads and find already running instances of
    ThreadingHTTPServer"""

    thread_list = threading.enumerate()
    ref_class_name = compare_class.__name__
    for thread in thread_list:
        thread_class_name = thread.__class__.__name__
        if ref_class_name == thread_class_name:
            if thread.is_alive():
                return True, thread

    return False, None
