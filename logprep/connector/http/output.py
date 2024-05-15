"""
Output Module that takes a batch of events and sends them to a http endpoint with given credentials
"""

import logging
import time
from functools import cached_property

import requests
from attrs import define, field, validators

from logprep.abc.output import Output

requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member

logger = logging.getLogger("HttpOutput")


class HttpOutput(Output):
    """Output that sends http post requests to a given endpoint with configured credentials"""

    @define(kw_only=True)
    class Config(Output.Config):
        user: str = field(validator=validators.instance_of(str), default="")
        password: str = field(validator=validators.instance_of(str), default="")
        events: int = field(
            validator=validators.instance_of(int),
            default=1,
            converter=lambda x: 1 if x is None else int(x),
        )
        target_url: str

    @property
    def user(self):
        return self._config.user

    @property
    def password(self):
        return self._config.password

    @cached_property
    def _headers(self):
        return {"Content-Type": "application/x-ndjson; charset=utf-8"}

    def __init__(self, name: str, config: "HttpOutput.Config"):
        super().__init__(name, config)
        self.event_sent = 0

    def store_custom(self, batch: tuple[str, dict] | dict) -> dict:
        """
        Send a batch of events to an endpoint and return the received status code times the number
        of events.
        """
        if isinstance(batch, tuple):
            event_target, request_data = batch
        else:
            event_target = self._config.target_url
            request_data = batch
        self._send_post_request(event_target, self._config.events, request_data)
        self.metrics.number_of_processed_events += 1

    def store(self, batch) -> dict:
        self.store_custom(batch)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.metrics.number_of_failed_events += 1
        pass

    def _send_post_request(self, event_target: str, number_events: int, request_data: str) -> dict:
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
