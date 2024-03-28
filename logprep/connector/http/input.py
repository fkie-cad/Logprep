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
        message_backlog_size: 15000
        collect_meta: False
        metafield_name: "@metadata"
        uvicorn_config:
            host: 0.0.0.0
            port: 9000
        endpoints:
            /firstendpoint: json
            /seccondendpoint: plaintext
            /thirdendpoint: jsonl
"""

import inspect
import queue
import threading
from abc import ABC
from logging import Logger
import logging
import re
from typing import Mapping, Tuple, Union, Callable
from attrs import define, field, validators
import msgspec
import uvicorn
import falcon.asgi
from falcon import HTTPTooManyRequests, HTTPMethodNotAllowed  # pylint: disable=no-name-in-module
from logprep.abc.input import FatalInputError, Input
from logprep.util import defaults

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]

# Config Parts that's checked for Config Change
HTTP_INPUT_CONFIG_KEYS = [
    "preprocessing",
    "uvicorn_config",
    "endpoints",
    "collect_meta",
    "metafield_name",
    "message_backlog_size",
]


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


def decorator_add_metadata(func: Callable):
    """Decorator to add metadata to resulting http event.
    Uses attribute collect_meta of endpoint class to decide over metadata collection
    Uses attribute metafield_name to define key name for metadata
    """

    async def func_wrapper(*args, **kwargs):
        req = args[1]
        endpoint = args[0]
        if endpoint.collect_meta:
            metadata = {
                "url": req.url,
                "remote_addr": req.remote_addr,
                "user_agent": req.user_agent,
            }
            kwargs["metadata"] = {endpoint.metafield_name: metadata}
        else:
            kwargs["metadata"] = {}
        func_wrapper = await func(*args, **kwargs)
        return func_wrapper

    return func_wrapper


def route_compile_helper(input_re_str: str):
    """falcon add_sink handles prefix routes as independent URI elements
    therefore we need regex position anchors to ensure beginning and
    end of given route and replace * with .* for user-friendliness
    """
    input_re_str = input_re_str.replace("*", ".*")
    input_re_str = "^" + input_re_str + "$"
    return re.compile(input_re_str)


class HttpEndpoint(ABC):
    """Interface for http endpoints.
    Additional functionality is added to child classes via removable decorators.

    Parameters
    ----------
    messages: queue.Queue
        Input Events are put here
    collect_meta: bool
        Collects Metadata on True (default)
    metafield_name: str
        Defines key name for metadata
    """

    def __init__(self, messages: queue.Queue, collect_meta: bool, metafield_name: str) -> None:
        self.messages = messages
        self.collect_meta = collect_meta
        self.metafield_name = metafield_name


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder = msgspec.json.Decoder()

    @decorator_request_exceptions
    @decorator_add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """json endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        metadata = kwargs.get("metadata", {})
        if data:
            event = self._decoder.decode(data)
            self.messages.put({**event, **metadata}, block=False)


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    _decoder = msgspec.json.Decoder()

    @decorator_request_exceptions
    @decorator_add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        data = await req.stream.read()
        data = data.decode("utf8")
        event = kwargs.get("metadata", {})
        metadata = kwargs.get("metadata", {})
        stripped_lines = map(str.strip, data.splitlines())
        events = (self._decoder.decode(line) for line in stripped_lines if line)
        for event in events:
            self.messages.put({**event, **metadata}, block=False)


class PlaintextHttpEndpoint(HttpEndpoint):
    """:code:`plaintext` endpoint to get the body from request
    and put it in :code:`message` field"""

    @decorator_request_exceptions
    @decorator_add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await req.stream.read()
        metadata = kwargs.get("metadata", {})
        event = {"message": data.decode("utf8")}
        print(event)
        self.messages.put({**event, **metadata}, block=False)


class ThreadingHTTPServer:  # pylint: disable=too-many-instance-attributes
    """Singleton Wrapper Class around Uvicorn Thread that controls
    lifecycle of Uvicorn HTTP Server. During Runtime this singleton object
    is stateful and therefore we need to check for some attributes during
    __init__ when multiple consecutive reconfigurations are happening.

    Parameters
    ----------
    connector_config: Input.Config
        Holds full connector config for config change checks
    endpoints_config: dict
        Endpoint paths as key and initiated endpoint objects as
        value
    log_level: str
        Log level to be set for uvicorn server
    """

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
        connector_config: Input.Config,
        endpoints_config: dict,
        log_level: str,
    ) -> None:
        """Creates object attributes with necessary configuration.
        As this class creates a singleton object, the existing server
        will be stopped and restarted on consecutively creations"""
        super().__init__()

        self.connector_config = connector_config
        self.endpoints_config = endpoints_config
        self.log_level = log_level

        if hasattr(self, "thread"):
            if self.thread.is_alive():  # pylint: disable=access-member-before-definition
                self._stop()
        self._start()

    def _start(self):
        """Collect all configs, initiate application server and webserver
        and run thread with uvicorn+falcon http server and wait
        until it is up (started)"""
        self.uvicorn_config = self.connector_config.uvicorn_config
        self._init_web_application_server(self.endpoints_config)
        log_config = self._init_log_config()
        self.compiled_config = uvicorn.Config(
            **self.uvicorn_config,
            app=self.app,
            log_level=self.log_level,
            log_config=log_config,
        )
        self.server = uvicorn.Server(self.compiled_config)
        self._override_runtime_logging()
        self.thread = threading.Thread(daemon=False, target=self.server.run)
        self.thread.start()
        while not self.server.started:
            continue

    def _stop(self):
        """Stop thread with uvicorn+falcon http server, wait for uvicorn
        to exit gracefully and join the thread"""
        if self.thread.is_alive():
            self.server.should_exit = True
            while self.thread.is_alive():
                continue
        self.thread.join()

    def _init_log_config(self) -> dict:
        """Use for Uvicorn same log formatter like for Logprep"""
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
        return log_config

    def _override_runtime_logging(self):
        """Uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        http_server_name = logging.getLogger("Logprep").name + " HTTPServer"
        for logger_name in ["uvicorn", "uvicorn.access"]:
            logging.getLogger(logger_name).removeHandler(logging.getLogger(logger_name).handlers[0])
            logging.getLogger(logger_name).addHandler(
                logging.getLogger("Logprep").parent.handlers[0]
            )
        logging.getLogger("uvicorn.access").name = http_server_name
        logging.getLogger("uvicorn.error").name = http_server_name

    def _init_web_application_server(self, endpoints_config: dict) -> None:
        "Init falcon application server and setting endpoint routes"
        self.app = falcon.asgi.App()  # pylint: disable=attribute-defined-outside-init
        for endpoint_path, endpoint in endpoints_config.items():
            self.app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))

    def shut_down(self):
        """Shutdown method to trigger http server shutdown externally"""
        self._stop()


class HttpConnector(Input):
    """Connector to accept log messages as http post requests"""

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
        """Configures maximum size of input message queue for this connector. When limit is reached
        the server will answer with 429 Too Many Requests. For reasonable throughput this shouldn't
        be smaller than default value of 15.000 messages.
        """

        collect_meta: str = field(validator=validators.instance_of(bool), default=True)
        """Defines if metadata should be collected 
        - :code:`True`: Collect metadata
        - :code:`False`: Won't collect metadata
        """

        metafield_name: str = field(validator=validators.instance_of(str), default="@metadata")
        """Defines the name of the key for the collected metadata fields"""

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
        self.messages = queue.Queue(
            self._config.message_backlog_size
        )  # pylint: disable=attribute-defined-outside-init

    def setup(self):
        """setup starts the actual functionality of this connector.
        By checking against pipeline_index we're assuring this connector
        only runs a single time for multiple processes.
        """

        super().setup()
        if not hasattr(self, "pipeline_index"):
            raise FatalInputError(
                self, "Necessary instance attribute `pipeline_index` could not be found."
            )
        # Start HTTP Input only when in first process
        if self.pipeline_index != 1:
            return

        endpoints_config = {}
        collect_meta = self._config.collect_meta
        metafield_name = self._config.metafield_name
        # preparing dict with endpoint paths and initialized endpoints objects
        for endpoint_path, endpoint_name in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_name)
            endpoints_config[endpoint_path] = endpoint_class(
                self.messages, collect_meta, metafield_name
            )

        self.http_server = ThreadingHTTPServer(  # pylint: disable=attribute-defined-outside-init
            connector_config=self._config,
            endpoints_config=endpoints_config,
            log_level=self._logger.level,
        )

    def _get_event(self, timeout: float) -> Tuple:
        """Returns the first message from the queue"""
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
        self.http_server.shut_down()
