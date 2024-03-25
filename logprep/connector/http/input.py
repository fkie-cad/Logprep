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
import queue
import threading
from abc import ABC
from logging import Logger
import logging
import re
from typing import Mapping, Tuple, Union, Callable
import msgspec
import uvicorn
from attrs import define, field, validators
import falcon.asgi
from falcon import HTTPTooManyRequests, HTTPMethodNotAllowed  # pylint: disable=no-name-in-module
from logprep.abc.input import FatalInputError, Input
from logprep.util import defaults

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]

# Config Parts that's checked for Config Change
HTTP_INPUT_CONFIG_KEYS = ["preprocessing", "uvicorn_config", "endpoints"]


def threadsafe_wrapper(func):
    """Decorator making sure that the decorated function is thread safe"""
    lock = threading.Lock()

    def func_wrapper(*args, **kwargs):
        with lock:
            func_wrapper = func(*args, **kwargs)
        return func_wrapper

    return func_wrapper


def has_config_changed(
    old_config: Input.Config, new_config: Input.Config, check_attrs=None
) -> bool:
    """Compare Input Connector Configs for specific areas
    specified in check_attrs
    For sake of simplicity JSON Strings are compared instead
    of compare nested dict key-values
    """
    if not new_config:
        return True
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


def decorator_request_exceptions(func: Callable):
    """Decorator to wrap http calls and raise exceptions"""

    async def func_wrapper(*args, **kwargs):
        try:
            if args[1].method == "POST":
                func_wrapper = await func(*args, **kwargs)
            else:
                raise HTTPMethodNotAllowed(["POST"])
        except queue.Full as exc:
            raise HTTPTooManyRequests(description="Logprep Message Queue is full.") from exc
        return func_wrapper

    return func_wrapper


class HttpEndpoint(ABC):
    """interface for http endpoints"""

    messages: queue.Queue

    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder = msgspec.json.Decoder()

    @decorator_request_exceptions
    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """json endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        self.messages.put(self._decoder.decode(data), block=False)


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    _decoder = msgspec.json.Decoder()

    @decorator_request_exceptions
    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        for line in data.splitlines():
            line = line.strip()
            if line:
                event = self._decoder.decode(line)
                self.messages.put(event, block=False)


class PlaintextHttpEndpoint(HttpEndpoint):
    """:code:`plaintext` endpoint to get the body from request
    and put it in :code:`message` field"""

    @decorator_request_exceptions
    async def __call__(self, req, resp):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await req.stream.read()
        self.messages.put({"message": data.decode("utf8")})


class ThreadingHTTPServer:
    """Threading Wrapper around Uvicorn Server"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(ThreadingHTTPServer, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        connector_config,
        endpoints_config: dict,
        log_level: str,
    ) -> None:
        super().__init__()

        server_continue = False
        if hasattr(self, "thread"):
            if self.thread.is_alive():  # pylint: disable=access-member-before-definition
                if has_config_changed(
                    connector_config,
                    self.connector_config,  # pylint: disable=access-member-before-definition
                    check_attrs=HTTP_INPUT_CONFIG_KEYS,
                ):
                    server_continue = False
                else:
                    server_continue = True

        if not server_continue:
            self.connector_config = connector_config
            self.endpoints_config = endpoints_config
            self.uvicorn_config = self.connector_config.uvicorn_config
            self._init_web_application_server(self.endpoints_config)
            log_config = self._init_log_config()
            self.compiled_config = uvicorn.Config(
                **self.uvicorn_config,
                app=self.app,
                log_level=log_level,
                log_config=log_config,
            )
            self._stop()
            self.server = uvicorn.Server(self.compiled_config)
            self._override_runtime_logging()
            self.thread = threading.Thread(daemon=False, target=self.server.run)
            self._start()

    @threadsafe_wrapper
    def _start(self):
        """Start thread with uvicorn+falcon http server and wait
        until it is up (started)"""
        self.thread.start()
        while not self.server.started:
            continue

    @threadsafe_wrapper
    def _stop(self):
        """Stop thread with uvicorn+falcon http server, wait for uvicorn
        to exit gracefully and join the thread"""
        if hasattr(self, "thread"):
            if self.thread.is_alive():
                self.server.should_exit = True
                while self.thread.is_alive():
                    continue
            self.thread.join()

    @threadsafe_wrapper
    def _init_log_config(self) -> dict:
        """Use for Uvicorn same log formatter like for Logprep"""
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
        return log_config

    @threadsafe_wrapper
    def _override_runtime_logging(self):
        """Uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        http_server_name = logging.getLogger("Logprep").name + " HTTPServer"
        for logger_name in ["uvicorn", "uvicorn.access"]:
            logging.getLogger(logger_name).removeHandler(logging.getLogger(logger_name).handlers[0])
            logging.getLogger(logger_name).addHandler(
                logging.getLogger("Logprep").parent.handlers[0]
            )
            logging.getLogger(logger_name).name = http_server_name

    def _init_web_application_server(self, endpoints_config: dict) -> None:
        "Init falcon application server and setting endpoint routes"
        self.app = falcon.asgi.App()
        for endpoint_path, endpoint in endpoints_config.items():
            self.app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))

    @threadsafe_wrapper
    def shut_down(self):
        """Shutdown method to trigger http server shutdown externally"""
        self._stop()


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

        message_backlog_size: int = field(
            validator=validators.instance_of((int, float)), default=15000
        )

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

    def setup(self):
        super().setup()
        if not hasattr(self, "pipeline_index"):
            raise FatalInputError(
                self, "Necessary instance attribute `pipeline_index` could not be found."
            )
        # Start HTTP Input only when in first process
        if self.pipeline_index != 1:
            return

        self.messages = queue.Queue(
            self._config.message_backlog_size
        )  # pylint: disable=attribute-defined-outside-init

        endpoints_config = {}
        for endpoint_path, endpoint_name in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_name)
            endpoints_config[endpoint_path] = endpoint_class(self.messages)

        self.http_server = ThreadingHTTPServer(  # pylint: disable=attribute-defined-outside-init
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
        return self.http_server.app

    def get_server_instance(self):
        """Return server instance from webserver thread"""
        return self.http_server.server

    def shut_down(self):
        """Raises Uvicorn HTTP Server internal stop flag and waits to join"""
        try:
            self.http_server.shut_down()
        except:
            pass
