"""
Output Module that takes a batch of events and sends them to a http endpoint with given credentials
"""
import logging
import time
from functools import cached_property

import msgspec
import requests

requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member


class Output:
    """Output that sends http post requests to a given endpoint with configured credentials"""

    @cached_property
    def _headers(self):
        return {"Content-Type": "application/x-ndjson; charset=utf-8"}

    def __init__(self, config: dict):
        self.config = config
        self.user = config.get("user")
        self.password = config.get("password")
        self.log = logging.getLogger("Output")
        self._encoder = msgspec.json.Encoder()
        self.max_events = config.get("events")
        self.event_sent = 0

    def send(self, batch) -> dict:
        """
        Send a batch of events to an endpoint and return the received status code times the number
        of events.
        """
        send_time_start = time.perf_counter()
        event_target, request_data = batch
        stats = self._send_post_request(event_target, len(request_data.splitlines()), request_data)
        stats.update({"Batch send time": time.perf_counter() - send_time_start})
        return stats

    def _send_post_request(self, event_target: str, number_events: int, request_data: str) -> dict:
        """Send a post request with given data to the specified endpoint"""
        try:
            response = requests.post(
                f"{event_target}",
                headers=self._headers,
                data=request_data,
                verify=False,
                auth=(self.user, self.password),
                timeout=2,
            )
            stats = {
                f"Requests http status {str(response.status_code)}": 1,
                f"Events http status {str(response.status_code)}": number_events,
            }
            self.log.debug("Servers response code is: %i", response.status_code)
        except requests.exceptions.ConnectionError as error:
            stats = {
                "Requests ConnectionError": 1,
                "Events ConnectionError": number_events,
            }
            self.log.error(error)
        except requests.exceptions.MissingSchema as error:
            raise ConnectionError(
                f"No schema set in target-url: {self.config.get('target_url')}"
            ) from error
        except requests.exceptions.ReadTimeout as error:
            stats = {"Requests Timeout": 1, "Events Timeout": number_events}
        return stats
