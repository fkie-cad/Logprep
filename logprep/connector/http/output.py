"""
Output Module that takes a batch of events and sends them to a http endpoint with given credentials
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

    @property
    def user(self):
        """Return the user that is used for the http request"""
        return self._config.user

    @property
    def password(self):
        """Return the password that is used for the http request"""
        return self._config.password

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
                and "warning" not in x.name  # blocklisted metric
                and "error" not in x.name,  # blocklisted metric
                getattr(self.metrics, metric.name).tracker.collect()[0].samples,
            )
            for sample in samples:
                key = (
                    getattr(self.metrics, metric.name).description
                    if metric.name != "status_codes"
                    else sample.labels.get("description")
                )
                stats[key] = int(sample.value)
        stats = json.dumps(stats, sort_keys=True, indent=4, separators=(",", ": "))
        return stats

    def store_custom(self, document: dict | tuple | list, target: str) -> None:
        """
        Send a batch of events to an endpoint and return the received status code times the number
        of events.
        """
        if isinstance(document, (tuple, list, dict)):
            self._send_post_request(target, document)
        else:
            error = TypeError(f"Document type {type(document)} is not supported")
            self.store_failed(str(error), document, document)

    def store(self, document: tuple[str, dict] | dict) -> None:
        if isinstance(document, tuple):
            target, document = document
            target = f"{self._config.target_url}{target}"
        else:
            target = self._config.target_url
        self.store_custom(document, target)

    def store_failed(self, error_message, document_received, document_processed) -> None:
        pass

    def _send_post_request(self, event_target: str, documents: dict | tuple | list) -> dict:
        """Send a post request with given data to the specified endpoint"""
        document_count = 0
        if isinstance(documents, (tuple, list)):
            request_data = self._encoder.encode_lines(documents)
            document_count = len(documents)
        elif isinstance(documents, dict):
            request_data = self._encoder.encode(documents)
            document_count = 1
        try:
            try:
                logger.debug(request_data)
                response = requests.post(
                    url=event_target,
                    headers=self._headers,
                    verify=False,
                    auth=(self.user, self.password),
                    timeout=2,
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
                if self.input_connector is not None:
                    self.input_connector.batch_finished_callback()
            except requests.RequestException as error:
                logger.error("Failed to send event: %s", str(error))
                logger.debug("Failed event: %s", documents)
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
