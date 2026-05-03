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
          /endpoint_with_multiple_credentials: json

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
        /endpoint_with_multiple_credentials:
          - username: user
            password: secret_password
          - username: user2
            password_file: examples/exampledata/config/user_password.txt

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

import asyncio
import typing
import zlib
from abc import ABC
from base64 import b64encode
from collections.abc import Mapping
from functools import cached_property

import aiohttp
import falcon
import falcon.asgi
import msgspec
from attrs import define, field, validators

from logprep.connector.http.input import (
    DEFAULT_META_HEADERS,
    add_metadata,
    basic_auth,
    logger,
    raise_request_exceptions,
    route_compile_helper,
)
from logprep.factory_error import InvalidConfigurationError
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.ng.abc.event import EventMetadata
from logprep.ng.abc.input import Input
from logprep.ng.event.log_event import LogEvent
from logprep.ng.util.async_helpers import StoppableTask
from logprep.ng.util.worker.types import SizeLimitedQueue
from logprep.util import http, rstr
from logprep.util.credentials import (
    BasicAuthCredentials,
    Credentials,
    CredentialsFactory,
)
from logprep.util.helper import add_fields_to


class HttpEndpoint(ABC):
    """Interface for http endpoints.
    Additional functionality is added to child classes via removable decorators.

    Parameters
    ----------
    messages: SizeLimitedQueue
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
        messages: SizeLimitedQueue,
        original_event_field: dict[str, str] | None,
        collect_meta: bool,
        metafield_name: str,
        credentials: list[Credentials] | Credentials | None,
        metrics: "HttpInput.Metrics",
        copy_headers_to_logs: set[str],
    ) -> None:
        self.messages = messages
        self.original_event_field = original_event_field
        self.copy_headers_to_logs = copy_headers_to_logs

        # Deprecated
        self.collect_meta = collect_meta

        self.metafield_name = metafield_name
        self.metrics = metrics
        self.basicauth_b64: list[str] = []

        self.credentials = None

        if credentials:
            credentials = [credentials] if isinstance(credentials, Credentials) else credentials
            for cred in credentials:
                if isinstance(cred, BasicAuthCredentials):
                    self.basicauth_b64.append(
                        b64encode(f"{cred.username}:{cred.password}".encode("utf-8")).decode(
                            "utf-8"
                        )
                    )
            self.credentials = credentials

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

    async def put_message(self, event: dict, metadata: dict):
        """Puts message to internal queue"""
        if self.metafield_name in event:
            logger.warning("metadata field was in event and got overwritten")
        await self.messages.put(event | metadata)


class JSONHttpEndpoint(HttpEndpoint):
    """:code:`json` endpoint to get json from request"""

    _decoder: msgspec.json.Decoder[dict] = msgspec.json.Decoder()

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
            await self.put_message(event, kwargs["metadata"])


class JSONLHttpEndpoint(HttpEndpoint):
    """:code:`jsonl` endpoint to get jsonl from request"""

    _decoder: msgspec.json.Decoder[dict] = msgspec.json.Decoder()

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

            await self.put_message(event, kwargs["metadata"])


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
        await self.put_message(event, kwargs["metadata"])


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
            if (
                self.preprocessing.add_full_event_to_target_field is not None
                and self.original_event_field
            ):
                raise InvalidConfigurationError(
                    "Cannot configure both add_full_event_to_target_field and original_event_field."
                )

    __slots__: list[str] = ["target", "app", "http_server", "messages"]

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
        self.http_server: http.AsyncHTTPServer | None = None
        self.messages: SizeLimitedQueue[dict] = SizeLimitedQueue(self.config.message_backlog_size)

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(HttpInput.Config, self._config)

    async def setup(self) -> None:
        """setup starts the actual functionality of this connector."""

        if self.messages is None:
            raise ValueError("message queue `messages` has not been set")

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

        self.http_server = http.AsyncHTTPServer(self.config.uvicorn_config, self.app)
        self._http_server_task = StoppableTask.from_stop(
            asyncio.create_task(self.http_server.run()), self.http_server.stop
        )
        # give the http server a chance to start before health checks begin
        await asyncio.sleep(0)

        await super().setup()

    @staticmethod
    def _get_asgi_app(endpoints_config: dict) -> falcon.asgi.App:
        """Init falcon application server and setting endpoint routes"""
        app = falcon.asgi.App()
        for endpoint_path, endpoint in endpoints_config.items():
            app.add_sink(endpoint, prefix=route_compile_helper(endpoint_path))
        return app

    async def _get_event(self, timeout: float) -> tuple[dict, bytes, EventMetadata] | None:
        """Returns the first message from the queue"""
        self.metrics.message_backlog_size += self.messages.qsize()
        try:
            async with asyncio.timeout(timeout):
                message = await self.messages.get()
            raw_message = str(message).encode("utf8")
            return message, raw_message, EventMetadata.from_dict({})
        except TimeoutError:
            return None

    async def shut_down(self):
        """Raises Uvicorn HTTP Server internal stop flag and waits to join"""
        await self._http_server_task.stop()
        await super().shut_down()

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

    async def health(self) -> bool:  # type: ignore[override]
        """Health check for the HTTP Input Connector

        Returns
        -------
        bool
            :code:`True` if all endpoints can be called without error
        """
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(self.config.health_timeout)
        ) as session:

            async def check_endpoint_status(endpoint: str) -> None:
                try:
                    async with session.get(f"{self.target}{endpoint}") as response:
                        response.raise_for_status()
                except (aiohttp.ClientError, TimeoutError) as error:
                    logger.error(
                        "Health check failed for endpoint: %s due to %s",
                        endpoint,
                        str(error),
                        exc_info=True,
                    )
                    raise

            try:
                await asyncio.gather(*map(check_endpoint_status, self.health_endpoints))
            except (aiohttp.ClientError, TimeoutError):
                self.metrics.number_of_errors += 1
                return False

        return await super().health()

    async def acknowledge(self, events: list[LogEvent]):
        logger.info("acknowledge called but not implemented")
