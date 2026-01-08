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
        original_event_field:
            "target_field": "event.original"
            "format": "dict"
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

The connector configuration includes an optional parameter called original_event_field.
When set, the full event is stored as a string or dictionary in a specified field. The
target field for this operation is set via the parameter `target_field` and the format
(string or dictionary) ist specified with the `format` parameter.

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
          password_file: examples/exampledata/config/user_password.txt
        /second*:
          username: user
          password: secret_password

You can choose between a plain secret with the key :code:`password` or a filebased secret
with the key :code:`password_file`.

.. security-best-practice::
   :title: Http Input Connector - Authentication

   When using basic auth with the http input connector
   the following points should be taken into account:

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

import logging
import multiprocessing as mp
import queue
import re
import typing
import zlib
from abc import ABC
from base64 import b64encode
from collections.abc import Callable, Mapping
from functools import cached_property
from multiprocessing import Queue

import falcon.asgi
import msgspec
import requests
from attrs import define, field, validators
from falcon import (  # pylint: disable=no-name-in-module
    HTTP_200,
    HTTPBadRequest,
    HTTPInternalServerError,
    HTTPMethodNotAllowed,
    HTTPTooManyRequests,
    HTTPUnauthorized,
)

from logprep.abc.input import FatalInputError, Input
from logprep.factory_error import InvalidConfigurationError
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.util import http, rstr
from logprep.util.credentials import Credentials, CredentialsFactory
from logprep.util.helper import add_fields_to

logger = logging.getLogger("HTTPInput")


def basic_auth(func: Callable):
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


def raise_request_exceptions(func: Callable):
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
                    raise queue.Full()
                return
            else:
                raise HTTPMethodNotAllowed(["POST"])
        except HTTPUnauthorized as error:
            raise error from error
        except queue.Full as error:
            raise HTTPTooManyRequests(description="Logprep Message Queue is full.") from error
        except msgspec.DecodeError as error:
            raise HTTPBadRequest(
                description=f"Can't decode message due to: {str(error)}"
            ) from error
        except Exception as error:  # pylint: disable=broad-except
            raise HTTPInternalServerError(
                description=f"Unexpected Exception: {str(error)}"
            ) from error
        return func_wrapper

    return func_wrapper


DEFAULT_META_HEADERS = frozenset(
    [
        "url",
        "remote_addr",
        "user-agent",
    ]
)


def add_metadata(func: Callable):
    """Decorator to add metadata to resulting http event.
    Uses attribute collect_meta of endpoint class to decide over metadata collection
    Uses attribute metafield_name to define key name for metadata
    """

    async def func_wrapper(*args, **kwargs):
        req: falcon.asgi.Request = args[1]
        endpoint: HttpEndpoint = args[0]

        if not endpoint.collect_meta or len(endpoint.copy_headers_to_logs) == 0:
            kwargs["metadata"] = {}
        else:
            metadata = {}
            for header in endpoint.copy_headers_to_logs:
                # remote_addr and url are special cases, because those are not copied 1 to 1 from headers
                match header:
                    case "remote_addr":
                        metadata[header] = req.remote_addr
                    case "url":
                        metadata[header] = req.url
                    case _:
                        key = header.replace("-", "_").lower()
                        metadata[key] = req.get_header(header, required=False, default=None)

            kwargs["metadata"] = {endpoint.metafield_name: metadata}

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

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        messages: mp.Queue,
        original_event_field: dict[str, str] | None,
        collect_meta: bool,
        metafield_name: str,
        credentials: Credentials | None,
        metrics: "HttpInput.Metrics",
        copy_headers_to_logs: set[str],
    ) -> None:
        self.messages = messages
        self.original_event_field = original_event_field
        self.copy_headers_to_logs = copy_headers_to_logs

        # Deprecated
        self.collect_meta = collect_meta
        self.metafield_name = metafield_name
        self.credentials = credentials
        self.metrics = metrics
        if self.credentials:
            # TODO what about other credential types?
            self.basicauth_b64 = b64encode(
                f"{self.credentials.username}:{self.credentials.password}".encode("utf-8")  # type: ignore
            ).decode("utf-8")

    def collect_metrics(self):
        """Increment number of requests"""
        self.metrics.number_of_http_requests += 1

    async def get_data(self, req: falcon.asgi.Request) -> bytes:
        """returns the data from the request body

        if the request has a Content-Encoding header with the value gzip, the data will be
        decompressed using zlib because according to
        https://docs.python.org/3/library/gzip.html#gzip.decompress
        zlib with wbits=31 is the faster implementation.

        Parameters
        ----------
        req : falcon.asgi.Request
            the incoming request

        Returns
        -------
        bytes
            data from the request body
        """
        data = await req.stream.readall()
        if encoding := req.get_header("Content-Encoding"):
            if encoding == "gzip":
                data = zlib.decompress(data, 31)
        return data

    def put_message(self, event: dict, metadata: dict):
        """Puts message to internal queue"""
        if self.metafield_name in event:
            logger.warning("metadata field was in event and got overwritten")
        self.messages.put(event | metadata, block=False)


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder = msgspec.json.Decoder()

    @raise_request_exceptions
    @basic_auth
    @add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """json endpoint method"""
        self.collect_metrics()
        data = await self.get_data(req)
        if data:
            event = self._decoder.decode(data)
            if self.original_event_field:
                target_field = self.original_event_field["target_field"]
                event_value = (
                    data.decode("utf8") if self.original_event_field["format"] == "str" else event
                )
                event = {}
                add_fields_to(event, {target_field: event_value})
            self.put_message(event, kwargs["metadata"])


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    _decoder = msgspec.json.Decoder()

    @raise_request_exceptions
    @basic_auth
    @add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """jsonl endpoint method"""
        self.collect_metrics()
        data = await self.get_data(req)
        events = self._decoder.decode_lines(data)
        for event in events:
            if self.original_event_field:
                target_field = self.original_event_field["target_field"]
                event_value = (
                    data.decode("utf8") if self.original_event_field["format"] == "str" else event
                )
                event = {}
                add_fields_to(event, {target_field: event_value})

            self.put_message(event, kwargs["metadata"])


class PlaintextHttpEndpoint(HttpEndpoint):
    """:code:`plaintext` endpoint to get the body from request
    and put it in :code:`message` field"""

    @raise_request_exceptions
    @basic_auth
    @add_metadata
    async def __call__(self, req, resp, **kwargs):  # pylint: disable=arguments-differ
        """plaintext endpoint method"""
        self.collect_metrics()
        data = await self.get_data(req)
        event = {"message": data.decode("utf8")}
        if self.original_event_field:
            target_field = self.original_event_field["target_field"]
            event_value = (
                data.decode("utf8") if self.original_event_field["format"] == "str" else event
            )
            event = {}
            add_fields_to(event, {target_field: event_value})
        self.put_message(event, kwargs["metadata"])


class HttpInput(Input):
    """Connector to accept log messages as http post requests"""

    @define(kw_only=True)
    class Metrics(Input.Metrics):
        """Tracks statistics about this connector"""

        number_of_http_requests: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of incoming requests",
                name="number_of_http_requests",
            )
        )
        """Number of incoming requests"""

        message_backlog_size: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Size of the message backlog queue",
                name="message_backlog_size",
            )
        )
        """Size of the message backlog queue"""

    @define(kw_only=True)
    class Config(Input.Config):
        """Config for HTTPInput"""

        uvicorn_config: dict[str, str | int] = field(
            validator=validators.deep_mapping(
                mapping_validator=validators.instance_of(dict),
                key_validator=validators.in_(http.UVICORN_CONFIG_KEYS),
                # lambda xyz tuple necessary because of input structure
                value_validator=lambda x, y, z: True,
            ),
        )

        """Configure uvicorn server. For possible settings see
        `uvicorn settings page <https://www.uvicorn.org/settings>`_.

        .. security-best-practice::
           :title: Uvicorn Webserver Configuration
           :location: uvicorn_config
           :suggested-value: uvicorn_config.access_log: true,
            uvicorn_config.server_header: false, uvicorn_config.date_header: false

           Additionally to the below it is recommended to configure
           `ssl` on the metrics server endpoint
           <https://www.uvicorn.org/settings/#https>`_

           .. code-block:: yaml

                uvicorn_config:
                    access_log: true
                    server_header: false
                    date_header: false
                    workers: 2

        """
        endpoints: dict[str, str] = field(
            validator=validators.deep_mapping(
                mapping_validator=validators.instance_of(dict),
                key_validator=validators.matches_re(r"^\/.+"),
                value_validator=validators.in_(["json", "plaintext", "jsonl"]),
            ),
        )
        """Configure endpoint routes with a Mapping of a path to an endpoint. Possible endpoints
        are: :code:`json`, :code:`jsonl`, :code:`plaintext`. It's possible to use wildcards and
        regexps for pattern matching.


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

        copy_headers_to_logs: set[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(str),
                iterable_validator=validators.or_(
                    validators.instance_of(set), validators.instance_of(list)
                ),
            ),
            converter=set,
            factory=lambda: set(DEFAULT_META_HEADERS),
        )
        """Defines what metadata should be collected from Http Headers
        Special cases:
        - remote_addr (Gets the inbound client ip instead of header)
        - url (Get the requested url from http request and not technically a header)

        Defaults:
        - remote_addr
        - url
        - User-Agent

        The output header names in Events are stored as json strings, and are transformed from "User-Agent" to "user_agent"
        """

        collect_meta: bool = field(validator=validators.instance_of(bool), default=True)
        """Deprecated use copy_headers_to_logs instead, to turn off collecting metadata set copy_headers_to_logs to an empty list ([]).
        Defines if metadata should be collected
        - :code:`True`: Collect metadata
        - :code:`False`: Won't collect metadata

        .. security-best-practice::
           :title: Input Connector - HttpConnector

           It is suggested to enable the collection of meta data (:code:`collect_meta: True`) to
           ensure transparency of the incoming events.
        """

        metafield_name: str = field(validator=validators.instance_of(str), default="@metadata")
        """Defines the name of the key for the collected metadata fields.
        Logs a Warning if metadata field overwrites preexisting field in Event
        """

        original_event_field: dict[str, str] | None = field(
            validator=validators.optional(
                validators.deep_mapping(
                    mapping_validator=validators.instance_of(dict),
                    key_validator=validators.in_(["format", "target_field"]),
                    value_validator=validators.instance_of(str),
                ),
            ),
            default=None,
        )
        """Optional config parameter that writes the full event to one single target field. The
        format can be specified with the parameter :code:`format`. Possible are :code:`str` and :code:`dict` where
        dict is the default format. The target field can be specified with the parameter
        :code:`target_field`."""

        def __attrs_post_init__(self):
            if "add_full_event_to_target_field" in self.preprocessing and self.original_event_field:
                raise InvalidConfigurationError(
                    "Cannot configure both add_full_event_to_target_field and original_event_field."
                )

    __slots__: list[str] = ["target", "app", "http_server"]

    messages: typing.Optional[Queue] = None

    _endpoint_registry: Mapping[str, type[HttpEndpoint]] = {
        "json": JSONHttpEndpoint,
        "plaintext": PlaintextHttpEndpoint,
        "jsonl": JSONLHttpEndpoint,
    }

    def __init__(self, name: str, configuration: "HttpInput.Config") -> None:
        super().__init__(name, configuration)
        port = self.config.uvicorn_config["port"]
        host = self.config.uvicorn_config["host"]
        ssl_options = any(
            setting for setting in self.config.uvicorn_config if setting.startswith("ssl")
        )
        schema = "https" if ssl_options else "http"
        self.target = f"{schema}://{host}:{port}"
        self.app: falcon.asgi.App | None = None
        self.http_server: http.ThreadingHTTPServer | None = None

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(HttpInput.Config, self._config)

    def setup(self) -> None:
        """setup starts the actual functionality of this connector.
        By checking against pipeline_index we're assuring this connector
        only runs a single time for multiple processes.
        """

        super().setup()

        if self.messages is None:
            raise ValueError("message queue `messages` has not been set")

        if self.pipeline_index is None:
            raise FatalInputError(self, "Necessary instance attribute `pipeline_index` is not set.")
        # Start HTTP Input only when in first process
        if self.pipeline_index != 1:
            return

        endpoints_config = {}
        collect_meta = self.config.collect_meta
        copy_headers_to_logs = self.config.copy_headers_to_logs
        metafield_name = self.config.metafield_name
        original_event_field = self.config.original_event_field
        cred_factory = CredentialsFactory()
        # preparing dict with endpoint paths and initialized endpoints objects
        # and add authentication if credentials are existing for path
        for endpoint_path, endpoint_type in self.config.endpoints.items():
            endpoint_class = self._endpoint_registry.get(endpoint_type)

            if endpoint_class is None:  # pragma: no cover this is a mypy issue fix
                continue

            credentials = cred_factory.from_endpoint(endpoint_path)
            endpoints_config[endpoint_path] = endpoint_class(
                self.messages,
                original_event_field,
                collect_meta,
                metafield_name,
                credentials,
                self.metrics,
                copy_headers_to_logs,
            )

        self.app = self._get_asgi_app(endpoints_config)
        self.http_server = http.ThreadingHTTPServer(
            self.config.uvicorn_config, self.app, daemon=False, logger_name="HTTPServer"
        )
        self.http_server.start()

    @staticmethod
    def _get_asgi_app(endpoints_config: dict) -> falcon.asgi.App:
        """Init falcon application server and setting endpoint routes"""
        app = falcon.asgi.App()
        for endpoint_path, endpoint in endpoints_config.items():
            app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))
        return app

    def _get_event(self, timeout: float) -> tuple:
        """Returns the first message from the queue"""
        messages = typing.cast(Queue, self.messages)

        self.metrics.message_backlog_size += messages.qsize()
        try:
            message = messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message
        except queue.Empty:
            return None, None

    def _shut_down(self):
        """Raises Uvicorn HTTP Server internal stop flag and waits to join"""
        if self.http_server:
            self.http_server.shut_down()
        return super()._shut_down()

    @cached_property
    def health_endpoints(self) -> list[str]:
        """Returns a list of endpoints for internal healthcheck
        the endpoints are examples to match against the configured regex enabled
        endpoints. The endpoints are normalized to match the regex patterns and
        this ensures that the endpoints should not be too long
        """
        normalized_endpoints = (endpoint.replace(".*", "b") for endpoint in self.config.endpoints)
        normalized_endpoints = (endpoint.replace(".+", "b") for endpoint in normalized_endpoints)
        normalized_endpoints = (endpoint.replace("+", "{5}") for endpoint in normalized_endpoints)
        normalized_endpoints = (endpoint.replace("*", "{5}") for endpoint in normalized_endpoints)
        return [rstr.xeger(endpoint) for endpoint in normalized_endpoints]

    def health(self) -> bool:
        """Health check for the HTTP Input Connector

        Returns
        -------
        bool
            :code:`True` if all endpoints can be called without error
        """
        for endpoint in self.health_endpoints:
            try:
                requests.get(
                    f"{self.target}{endpoint}", timeout=self.config.health_timeout
                ).raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as error:
                logger.error("Health check failed for endpoint: %s due to %s", endpoint, str(error))
                self.metrics.number_of_errors += 1
                return False

        return super().health()
