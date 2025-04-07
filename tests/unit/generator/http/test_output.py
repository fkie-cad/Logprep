# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from unittest.mock import MagicMock

import pytest
import responses

from tests.unit.connector.base import BaseOutputTestCase
from tests.unit.connector.test_http_output import TestOutput

TARGET_URL = "https://www.test.de"


class TestHttpGeneratorOutput(TestOutput):

    CONFIG = {
        "type": "http_generator_output",
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
        document = "/123,{'event1_key': 'event1_value'};{'event2_key': 'event2_value'}"
        self.object.store(document)
        assert self.object.metrics.number_of_processed_events == 2

    def test_store_calls_store_custom(self):
        self.object.store_custom = MagicMock()
        self.object.store("/test_path,test_payload")
        self.object.store_custom.assert_called_once_with(
            "test_payload", "https://www.test.de/test_path"
        )

    def test_store_handles_empty_payload(self):
        self.object.store_custom = MagicMock()
        self.object.store("/test_path,")
        self.object.store_custom.assert_called_once_with("", "https://www.test.de/test_path")

    def test_store_handles_missing_comma(self):
        self.object.store_custom = MagicMock()
        self.object.store("/test_path")
        self.object.store_custom.assert_called_once_with("", "https://www.test.de/test_path")

    @pytest.mark.parametrize(
        "testcase, input_data, number_of_expected_requests, number_of_expected_events",
        [
            ("/test", '{"message": "my event message"}', 1, 1),
            ("/test", '{"message": "my event message"};{"message": "my event message"}', 1, 2),
        ],
    )
    @responses.activate
    def test_store_counts_number_of_requests_and_events(
        self, testcase, input_data, number_of_expected_requests, number_of_expected_events
    ):

        target_url = TARGET_URL
        responses.add(responses.POST, f"{target_url}{testcase}", status=200)
        self.object.metrics.number_of_processed_events = 0
        self.object.metrics.number_of_http_requests = 0
        self.object.metrics.number_of_failed_events = 0
        self.object.store(testcase + "," + input_data)
        assert (
            self.object.metrics.number_of_failed_events == 0
        ), f"no failed events for input {input_data}"
        assert self.object.metrics.number_of_processed_events == number_of_expected_events
        assert self.object.metrics.number_of_http_requests == number_of_expected_requests
