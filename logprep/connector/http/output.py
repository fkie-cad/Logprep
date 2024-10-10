"""
HTTPOutput
==========

A http output connector that sends http post requests to paths under a given endpoint


HTTP Output Connector Config Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An example config file would look like:

..  code-block:: yaml
    :linenos:

    output:
      myhttpoutput:
        type: http_output
        target_url: http://the.target.url:8080
        username: user
        password: password

The :code:`store` method of this connector can be fed with a :code:`dictionary` or a :code:`tuple`.
If a :code:`tuple` is passed, the first element is the target path and
the second element is the event or a list of events.
If a :code:`dictionary` is passed, the event will be send to the configured root
of the :code:`target_url`.

.. security-best-practice::
   :title: Http Output Connector - Usage

   This Connector is currently only used in the log generator and does not have a stable interface.
   Do not use this in production.

.. security-best-practice::
   :title: Http Output Connector - SSL

   This connector does not verify the SSL Context, which could lead to exposing sensitive data.

"""

import json
import logging
from functools import cached_property

import requests
from attrs import define, field, validators

from logprep.abc.output import Output
from logprep.metrics.metrics import CounterMetric

logger = logging.getLogger("HttpOutput")


class HttpOutput(Output):
    """Output that sends http post requests to paths under a given endpoint
    with configured credentials"""

    @define(kw_only=True)
    class Metrics(Output.Metrics):
        """Tracks statistics about this connector"""

        number_of_failed_events: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of failed events",
                name="number_of_failed_events",
            )
        )
        """Number of failed events"""

        number_of_http_requests: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Requests total",
                name="number_of_http_requests",
            )
        )
        """Requests total"""

        status_codes: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Requests http status",
                name="status_codes",
                inject_label_values=False,
            ),
        )
        """Requests http status"""

        connection_errors: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Requests Connection Errors",
                name="connection_errors",
            ),
        )
        """Requests Connection Errors"""

        timeouts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Requests Timeouts",
                name="timeouts",
            ),
        )
        """Requests Timeouts"""

    @define(kw_only=True)
    class Config(Output.Config):
        """Configuration for the HttpOutput."""

        user: str = field(
            validator=validators.instance_of(str),
            default="",
            converter=lambda x: "" if x is None else x,
        )
        """User that is used for the basic auth http request"""
        password: str = field(
            validator=validators.instance_of(str),
            default="",
            converter=lambda x: "" if x is None else x,
        )
        """Password that is used for the basic auth http request"""
        target_url: str
        """URL of the endpoint that receives the events"""
        timeout: int = field(validator=validators.instance_of(int), default=2)
        """Timeout in seconds for the http request"""

    @property
    def user(self):
        """Return the user that is used for the http request"""
        return self._config.user

    @property
    def password(self):
        """Return the password that is used for the http request"""
        return self._config.password

    @property
    def timeout(self):
        """Return the timeout in seconds for the http request"""
        return self._config.timeout

    @cached_property
    def _headers(self):
        return {"Content-Type": "application/x-ndjson; charset=utf-8"}

    @property
    def statistics(self) -> str:
        """Return the statistics of this connector as a formatted string."""
        stats: dict = {}
        metrics = filter(lambda x: not x.name.startswith("_"), self.metrics.__attrs_attrs__)
        for metric in metrics:
            samples = filter(
                lambda x: x.name.endswith("_total")
                and "number_of_warnings" not in x.name  # blocklisted metric
                and "number_of_errors" not in x.name,  # blocklisted metric
                getattr(self.metrics, metric.name).tracker.collect()[0].samples,
            )
            for sample in samples:
                key = (
                    getattr(self.metrics, metric.name).description
                    if metric.name != "status_codes"
                    else sample.labels.get("description")
                )
                stats[key] = int(sample.value)
        return json.dumps(stats, sort_keys=True, indent=4, separators=(",", ": "))

    def store(self, document: tuple[str, dict | list[dict]] | dict) -> None:
        if isinstance(document, tuple):
            target, document = document
            target = f"{self._config.target_url}{target}"
        else:
            target = self._config.target_url
        self.store_custom(document, target)

    def store_custom(self, document: dict | tuple | list, target: str) -> None:
        """Send a post request with given data to the specified endpoint"""
        if isinstance(document, (tuple, list)):
            request_data = self._encoder.encode_lines(document)
            document_count = len(document)
        elif isinstance(document, dict):
            request_data = self._encoder.encode(document)
            document_count = 1
        else:
            error = TypeError(f"Document type {type(document)} is not supported")
            self.metrics.number_of_failed_events += 1
            logger.error(str(error))
            return
        try:
            try:
                logger.debug(request_data)
                response = requests.post(
                    url=target,
                    headers=self._headers,
                    verify=False,
                    auth=(self.user, self.password),
                    timeout=(self.timeout, self.timeout),
                    data=request_data,
                )
                logger.debug("Servers response code is: %i", response.status_code)
                self.metrics.status_codes.add_with_labels(
                    1,
                    {
                        "description": f"{self.metrics.status_codes.description} {response.status_code}"
                    },
                )
                response.raise_for_status()
                self.metrics.number_of_processed_events += document_count
                self.metrics.number_of_http_requests += 1
            except requests.RequestException as error:
                logger.error("Failed to send event: %s", str(error))
                logger.debug("Failed event: %s", document)
                self.metrics.number_of_failed_events += document_count
                self.metrics.number_of_http_requests += 1
                if not isinstance(error, requests.exceptions.HTTPError):
                    raise error
        except requests.exceptions.ConnectionError as error:
            logger.error(error)
            self.metrics.connection_errors += 1
            if isinstance(error, requests.exceptions.Timeout):
                self.metrics.timeouts += 1
        except requests.exceptions.MissingSchema as error:
            raise ConnectionError(
                f"No schema set in target-url: {self._config.get('target_url')}"
            ) from error
        except requests.exceptions.Timeout as error:
            # other timeouts than connection timeouts are handled here
            logger.error(error)
            self.metrics.timeouts += 1
