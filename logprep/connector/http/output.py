"""
Output Module that takes a batch of events and sends them to a http endpoint with given credentials
"""

import logging
from functools import cached_property

import requests
from attrs import define, field, validators

from logprep.abc.output import Output

logger = logging.getLogger("HttpOutput")


class HttpOutput(Output):
    """Output that sends http post requests to paths under a given endpoint
    with configured credentials"""

    @define(kw_only=True)
    class Config(Output.Config):
        """Configuration for the HttpOutput."""

        user: str = field(validator=validators.instance_of(str), default="")
        """User that is used for the basic auth http request"""
        password: str = field(validator=validators.instance_of(str), default="")
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

    def store_custom(self, document: dict, target: str):
        """
        Send a batch of events to an endpoint and return the received status code times the number
        of events.
        """
        self._send_post_request(target, document)
        self.metrics.number_of_processed_events += 1

    def store(self, document: tuple[str, dict] | dict) -> dict:
        if isinstance(document, tuple):
            target, document = document
        else:
            target = self._config.target_url
        self.store_custom(document, target)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.metrics.number_of_failed_events += 1

    def _send_post_request(self, event_target: str, request_data: str) -> dict:
        """Send a post request with given data to the specified endpoint"""
        try:
            try:
                response = requests.post(
                    f"{event_target}",
                    headers=self._headers,
                    data=request_data,
                    verify=False,
                    auth=(self.user, self.password),
                    timeout=2,
                )
                logger.debug("Servers response code is: %i", response.status_code)
                response.raise_for_status()
                if self.input_connector is not None:
                    self.input_connector.batch_finished_callback()
            except requests.RequestException as error:
                self.store_failed(str(error), request_data, request_data)
                if not isinstance(error, requests.exceptions.HTTPError):
                    raise error
        except requests.exceptions.ConnectionError as error:
            logger.error(error)
            # TODO update connection error metric
        except requests.exceptions.MissingSchema as error:
            raise ConnectionError(
                f"No schema set in target-url: {self._config.get('target_url')}"
            ) from error
        except requests.exceptions.ReadTimeout as error:
            # TODO update timout metric
            pass
