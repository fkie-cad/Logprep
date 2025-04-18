# pylint: disable=missing-docstring
import json
from unittest.mock import MagicMock, patch

import pytest
import requests
import responses
from requests.exceptions import SSLError

from tests.unit.connector.base import BaseOutputTestCase

TARGET_URL = "https://www.test.de"


class TestOutput(BaseOutputTestCase):

    CONFIG = {
        "type": "http_output",
        "target_url": TARGET_URL,
        "user": "user",
        "password": "password",
        "verify": "False",
    }

    expected_metrics = [
        *BaseOutputTestCase.expected_metrics,
        "logprep_number_of_http_requests",
        "logprep_status_codes",
        "logprep_timeouts",
        "logprep_connection_errors",
        "logprep_number_of_failed_events",
    ]

    @responses.activate
    def test_one_repeat(self):
        self.object.metrics.number_of_processed_events = 0
        responses.add(responses.POST, f"{TARGET_URL}/123", status=200)
        events = [{"event1_key": "event1_value"}, {"event2_key": "event2_value"}]
        batch = ("/123", events)
        self.object.store(batch)
        assert self.object.metrics.number_of_processed_events == 2

    @responses.activate
    def test_404_status_code(self):
        self.object.metrics.number_of_failed_events = 0
        self.object.metrics.number_of_processed_events = 0
        self.object.metrics.number_of_http_requests = 0
        responses.add(responses.POST, f"{TARGET_URL}/123", status=404)
        events = '{"event1_key": "event1_value", "event2_key": "event2_value"}'
        batch = f"/123,{events}"
        self.object.store(batch)
        assert self.object.metrics.number_of_failed_events == 1
        assert self.object.metrics.number_of_processed_events == 0
        assert self.object.metrics.number_of_http_requests == 1

    @pytest.mark.parametrize(
        "testcase, input_data, number_of_expected_requests, number_of_expected_events",
        [
            ("dict to root", {"message": "my event message"}, 1, 1),
            ("dict to target", ("/abc", {"message": "my event message"}), 1, 1),
            (
                "list to target",
                ("/abc", [{"message": "my event message"}, {"message": "my event message"}]),
                1,
                2,
            ),
            (
                "tuple to target",
                ("/abc", ({"message": "my event message"}, {"message": "my event message"})),
                1,
                2,
            ),
        ],
    )
    @responses.activate
    def test_store_counts_number_of_requests_and_events(
        self, testcase, input_data, number_of_expected_requests, number_of_expected_events
    ):
        if isinstance(input_data, tuple):
            target_url = input_data[0]
            target_url = f"{TARGET_URL}{target_url}"
        else:
            target_url = TARGET_URL
        responses.add(responses.POST, f"{target_url}", status=200)
        self.object.metrics.number_of_processed_events = 0
        self.object.metrics.number_of_http_requests = 0
        self.object.metrics.number_of_failed_events = 0
        self.object.store(input_data)
        assert (
            self.object.metrics.number_of_failed_events == 0
        ), f"no failed events for input {testcase}"
        assert self.object.metrics.number_of_processed_events == number_of_expected_events
        assert self.object.metrics.number_of_http_requests == number_of_expected_requests

    @pytest.mark.parametrize(
        "testcase, input_data",
        [
            ("generator", (a for a in range(10))),
            ("set", {1, 2, 3}),
            ("int", 123),
            ("float", 123.123),
            ("str", "123"),
        ],
    )
    def test_send_not_supported_input_data(self, testcase, input_data):
        self.object.metrics.number_of_failed_events = 0
        self.object.store_custom(123, input_data)
        assert self.object.metrics.number_of_failed_events == 1, testcase

    @responses.activate
    def test_store_counts_http_status_codes(self):
        responses.add(responses.POST, f"{TARGET_URL}/", status=200)
        responses.add(responses.POST, f"{TARGET_URL}/notfound", status=404)
        responses.add(responses.POST, f"{TARGET_URL}/transport-error", status=429)
        responses.add(responses.POST, f"{TARGET_URL}/success", status=200)
        self.object.store_custom({"message": "my event message"}, TARGET_URL)
        self.object.store_custom({"message": "my event message"}, f"{TARGET_URL}/success")
        self.object.store_custom({"message": "my event message"}, f"{TARGET_URL}/notfound")
        self.object.store_custom({"message": "my event message"}, f"{TARGET_URL}/transport-error")
        stats = json.loads(self.object.statistics)
        assert stats.get("Requests http status 200") == 2
        assert stats.get("Requests http status 404") == 1
        assert stats.get("Requests http status 429") == 1
        assert stats.get("Requests total") == 4

    @responses.activate
    def test_store_counts_connection_error(self):
        responses.add(responses.POST, f"{TARGET_URL}/", body=requests.exceptions.ConnectionError())
        self.object.store_custom({"message": "my event message"}, TARGET_URL)
        stats = json.loads(self.object.statistics)
        assert stats.get("Requests Connection Errors") == 1
        assert stats.get("Requests total") == 1

    @responses.activate
    def test_store_counts_connection_timeouts(self):
        responses.add(responses.POST, f"{TARGET_URL}/", body=requests.exceptions.ReadTimeout())
        self.object.store_custom({"message": "my event message"}, TARGET_URL)
        stats = json.loads(self.object.statistics)
        assert stats.get("Requests Timeouts") == 1
        assert stats.get("Requests total") == 1

    @responses.activate
    def test_store_counts_processed_events(self):
        responses.add(responses.POST, f"{TARGET_URL}/")
        self.object.metrics.number_of_processed_events = 0
        self.object.store("," + '"message": "my event message"')
        assert self.object.metrics.number_of_processed_events == 1

    @pytest.mark.skip(reason="not implemented")
    def test_setup_calls_wait_for_health(self):
        pass

    @responses.activate
    def test_respond_verify_unverified_host(self):
        with patch("requests.post", side_effect=SSLError("SSL certificate verify failed")):
            with patch.object(self.object.__class__, "verify", new=True):
                try:
                    self.object.store("," + '"message": "my event message"')
                except SSLError as e:
                    assert "SSL certificate verify failed" in str(e)

    @responses.activate
    def test_response_verify_verified_host(self):

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Success"

        with patch("requests.post", return_value=mock_response) as mock_post:
            with patch.object(self.object.__class__, "verify", new=True):
                self.object.store("," + '"message": "my event message"')

                mock_post.assert_called_once()
                assert mock_post.call_args.kwargs["verify"] is True

                assert mock_response.status_code == 200
                assert mock_response.text == "Success"
