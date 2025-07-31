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

import queue
from functools import cached_property
from typing import Mapping, Type

import falcon
import requests
from attrs import define, field, validators
from joblib._multiprocessing_helpers import mp

from logprep.connector.http.input import (
    HttpEndpoint,
    JSONHttpEndpoint,
    JSONLHttpEndpoint,
    PlaintextHttpEndpoint,
    logger,
    route_compile_helper,
)
from logprep.factory_error import InvalidConfigurationError
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.ng.abc.input import FatalInputError, Input
from logprep.util import http, rstr
from logprep.util.credentials import CredentialsFactory


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

        uvicorn_config: Mapping[str, str | int] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(http.UVICORN_CONFIG_KEYS),
                    # lambda xyz tuple necessary because of input structure
                    value_validator=lambda x, y, z: True,
                ),
            ]
        )

        """Configure uvicorn server. For possible settings see
        `uvicorn settings page <https://www.uvicorn.org/settings>`_.

        .. security-best-practice::
           :title: Uvicorn Webserver Configuration
           :location: uvicorn_config
           :suggested-value: uvicorn_config.access_log: true,
            uvicorn_config.server_header: false, uvicorn_config.data_header: false

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

        original_event_field: dict = field(
            validator=[
                validators.optional(
                    validators.deep_mapping(
                        key_validator=validators.in_(["format", "target_field"]),
                        value_validator=validators.instance_of(str),
                    )
                ),
            ],
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

    messages: mp.Queue = None

    _endpoint_registry: Mapping[str, Type[HttpEndpoint]] = {
        "json": JSONHttpEndpoint,
        "plaintext": PlaintextHttpEndpoint,
        "jsonl": JSONLHttpEndpoint,
    }

    def __init__(self, name: str, configuration: "HttpInput.Config") -> None:
        super().__init__(name, configuration)
        port = self._config.uvicorn_config["port"]
        host = self._config.uvicorn_config["host"]
        ssl_options = any(
            setting for setting in self._config.uvicorn_config if setting.startswith("ssl")
        )
        schema = "https" if ssl_options else "http"
        self.target = f"{schema}://{host}:{port}"
        self.app = None
        self.http_server: http.ThreadingHTTPServer | None = None

    def setup(self) -> None:
        """setup starts the actual functionality of this connector.
        By checking against pipeline_index we're assuring this connector
        only runs a single time for multiple processes.
        """

        super().setup()
        if self.pipeline_index is None:
            raise FatalInputError(self, "Necessary instance attribute `pipeline_index` is not set.")
        # Start HTTP Input only when in first process
        if self.pipeline_index != 1:
            return

        endpoints_config = {}
        collect_meta = self._config.collect_meta
        metafield_name = self._config.metafield_name
        original_event_field = self._config.original_event_field
        cred_factory = CredentialsFactory()
        # preparing dict with endpoint paths and initialized endpoints objects
        # and add authentication if credentials are existing for path
        for endpoint_path, endpoint_type in self._config.endpoints.items():
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
            )

        self.app = self._get_asgi_app(endpoints_config)
        self.http_server = http.ThreadingHTTPServer(
            self._config.uvicorn_config, self.app, daemon=False, logger_name="HTTPServer"
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

        self.metrics.message_backlog_size += self.messages.qsize()

        try:
            message = self.messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message, None
        except queue.Empty:
            return None, None, None

    def shut_down(self) -> None:
        """Raises Uvicorn HTTP Server internal stop flag and waits to join"""
        if self.http_server is None:  # pragma: no cover this is a mypy issue fix
            return
        self.http_server.shut_down()

    @cached_property
    def health_endpoints(self) -> list[str]:
        """Returns a list of endpoints for internal healthcheck
        the endpoints are examples to match against the configured regex enabled
        endpoints. The endpoints are normalized to match the regex patterns and
        this ensures that the endpoints should not be too long
        """
        normalized_endpoints = (endpoint.replace(".*", "b") for endpoint in self._config.endpoints)
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
                    f"{self.target}{endpoint}", timeout=self._config.health_timeout
                ).raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as error:
                logger.error("Health check failed for endpoint: %s due to %s", endpoint, str(error))
                self.metrics.number_of_errors += 1
                return False

        return super().health()
