"""
HTTPInput
==========

A http input connector that spawns an uvicorn server and accepts http requests, parses them,
puts them to an internal queue and pops them via :code:`get_next` method.


HTTP Connector Config Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An example config file would look like:

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
          /second*: plaintext
          /(third|fourth)/endpoint: jsonl
            
The endpoint config supports regex and wildcard patterns:
  * :code:`/second*`: matches everything after asterisk
  * :code:`/(third|fourth)/endpoint` matches either third or forth in the first part


Endpoint Credentials Config Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
By providing a credentials file in environment variable :code:`LOGPREP_CREDENTIALS_FILE` you can
add basic authentication for a specific endpoint. The format of this file would look like:

..  code-block:: yaml
    :caption: Example for credentials file 
    :linenos:

    input:
      endpoints:
        /firstendpoint:
          username: user
          password_file: quickstart/exampledata/config/user_password.txt
        /second*:
          username: user
          password: secret_password
          
You can choose between a plain secret with the key :code:`password` or a filebased secret
with the key :code:`password_file`.

.. security-best-practice::
   :title: Http Input Connector - Authentication

    When using basic auth with the http input connector the following points should be taken into account:
        - basic auth must only be used with strong passwords
        - basic auth must only be used with TLS encryption
        - avoid to reveal your plaintext secrets in public repositories
        
Behaviour of HTTP Requests
^^^^^^^^^^^^^^^^^^^^^^^^^^
  * :code:`GET`:
   
    * Responds always with 200 (ignores configured Basic Auth)
    * When Messages Queue is full, it responds with 429
  * :code:`POST`:
  
    * Responds with 200 on non-Basic Auth Endpoints
    * Responds with 401 on Basic Auth Endpoints (and 200 with appropriate credentials)
    * When Messages Queue is full, it responds wiht 429
  * :code:`ALL OTHER`:
  
    * Responds with 405
"""

import inspect
import logging
import multiprocessing as mp
import queue
import re
import threading
from abc import ABC
from base64 import b64encode
from logging import Logger
from typing import Callable, Mapping, Tuple, Union

import falcon.asgi
import msgspec
import uvicorn
from attrs import define, field, validators
from falcon import (  # pylint: disable=no-name-in-module
    HTTP_200,
    HTTPMethodNotAllowed,
    HTTPTooManyRequests,
    HTTPUnauthorized,
)

from logprep.abc.input import FatalInputError, Input
from logprep.util import defaults
from logprep.util.credentials import CredentialsFactory

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]


def decorator_basic_auth(func: Callable):
    """Decorator to check basic authentication.
    Will raise 401 on wrong credentials or missing Authorization-Header"""

    async def func_wrapper(*args, **kwargs):
        endpoint = args[0]
        req = args[1]
        if endpoint.credentials:
            auth_request_header = req.get_header("Authorization")
            if not auth_request_header:
                raise HTTPUnauthorized
            basic_string = req.auth
            if endpoint.basicauth_b64 not in basic_string:
                raise HTTPUnauthorized
        func_wrapper = await func(*args, **kwargs)
        return func_wrapper

    return func_wrapper


def decorator_request_exceptions(func: Callable):
    """Decorator to wrap http calls and raise exceptions"""

    async def func_wrapper(*args, **kwargs):
        try:
            if args[1].method == "POST":
                func_wrapper = await func(*args, **kwargs)
            elif args[1].method == "GET":
                endpoint = args[0]
                resp = args[2]
                resp.status = HTTP_200
                if endpoint.messages.full():
                    raise HTTPTooManyRequests(description="Logprep Message Queue is full.")
                return
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
    messages: mp.Queue
        Input Events are put here
    collect_meta: bool
        Collects Metadata on True (default)
    metafield_name: str
        Defines key name for metadata
    credentials: dict
        Includes authentication credentials, if unset auth is disabled
    """

    def __init__(
        self,
        messages: mp.Queue,
        collect_meta: bool,
        metafield_name: str,
        credentials: dict,
    ) -> None:
        self.messages = messages
        self.collect_meta = collect_meta
        self.metafield_name = metafield_name
        self.credentials = credentials
        if self.credentials:
            self.basicauth_b64 = b64encode(
                f"{self.credentials.username}:{self.credentials.password}".encode("utf-8")
            ).decode("utf-8")


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder = msgspec.json.Decoder()

    @decorator_request_exceptions
    @decorator_basic_auth
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
    @decorator_basic_auth
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
    @decorator_basic_auth
    @decorator_add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        data = await req.stream.read()
        metadata = kwargs.get("metadata", {})
        event = {"message": data.decode("utf8")}
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
        are: :code:`json`, :code:`jsonl`, :code:`plaintext`. It's possible to use wildcards and
        regexes for pattern matching.
        
        
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

        .. security-best-practice::
           :title: Input Connector - HttpConnector

           It is suggested to enable the collection of meta data (:code:`collect_meta: True`) to
           ensure transparency of the incoming events.
        """

        metafield_name: str = field(validator=validators.instance_of(str), default="@metadata")
        """Defines the name of the key for the collected metadata fields"""

    __slots__ = []

    messages: mp.Queue = None

    _endpoint_registry: Mapping[str, HttpEndpoint] = {
        "json": JSONHttpEndpoint,
        "plaintext": PlaintextHttpEndpoint,
        "jsonl": JSONLHttpEndpoint,
    }

    def __init__(self, name: str, configuration: "HttpConnector.Config", logger: Logger) -> None:
        super().__init__(name, configuration, logger)
        internal_uvicorn_config = {
            "lifespan": "off",
            "loop": "asyncio",
            "timeout_graceful_shutdown": 5,
        }
        self._config.uvicorn_config.update(internal_uvicorn_config)
        self.port = self._config.uvicorn_config["port"]
        self.host = self._config.uvicorn_config["host"]
        self.target = f"http://{self.host}:{self.port}"

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

        self._logger.debug(
            f"HttpInput Connector started on target {self.target} and "
            f"queue {id(self.messages)} "
            f"with queue_size: {self.messages._maxsize}"  # pylint: disable=protected-access
        )
        # Start HTTP Input only when in first process
        if self.pipeline_index != 1:
            return

        endpoints_config = {}
        collect_meta = self._config.collect_meta
        metafield_name = self._config.metafield_name
        cred_factory = CredentialsFactory()
        # preparing dict with endpoint paths and initialized endpoints objects
        # and add authentication if credentials are existing for path
        for endpoint_path, endpoint_type in self._config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_type)
            credentials = cred_factory.from_endpoint(endpoint_path)
            endpoints_config[endpoint_path] = endpoint_class(
                self.messages, collect_meta, metafield_name, credentials
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
        if not hasattr(self, "http_server"):
            return
        self.http_server.shut_down()
