# pylint: disable=missing-docstring
from unittest import mock

import pytest
import responses

from logprep.connector.http.output import HttpOutput
from tests.unit.connector.base import BaseOutputTestCase

TARGET_URL = "https://www.test.de"


class TestOutput(BaseOutputTestCase):

    CONFIG = {
        "type": "http_output",
        "target_url": TARGET_URL,
        "user": "user",
        "password": "password",
    }

    @responses.activate
    def test_one_repeat(self):
        self.object.metrics.number_of_processed_events = 0
        responses.add(responses.POST, f"{TARGET_URL}/123", status=200)
        events_string = """[{"event1_key": "event1_value"}\n{"event2_key": "event2_value"}]"""
        batch = (f"{TARGET_URL}/123", events_string)
        self.object.store(batch)
        assert self.object.metrics.number_of_processed_events == 1

    @responses.activate
    def test_404_status_code(self):
        self.object.metrics.number_of_failed_events = 0
        responses.add(responses.POST, f"{TARGET_URL}/123", status=404)
        events_string = """[{"event1_key": "event1_value"}\n{"event2_key": "event2_value"}]"""
        batch = (f"{TARGET_URL}/123", events_string)
        self.object.store(batch)
        assert self.object.metrics.number_of_failed_events == 1

    @responses.activate
    def test_store_calls_batch_finished_callback(self):
        responses.add(responses.POST, f"{TARGET_URL}/", status=200)
        self.object.input_connector = mock.MagicMock()
        self.object.store({"message": "my event message"})
        self.object.input_connector.batch_finished_callback.assert_called()
