# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use

import json
from unittest import mock

import pytest

from logprep.abc.output import CriticalOutputError
from logprep.factory import Factory
from tests.unit.connector.base import BaseOutputTestCase
from tests.unit.connector.test_confluent_kafka_common import CommonConfluentKafkaTestCase


class TestConfluentKafkaOutput(BaseOutputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "confluentkafka_output",
        "bootstrapservers": ["testserver:9092"],
        "topic": "test_input_raw",
        "error_topic": "test_error_topic",
        "flush_timeout": 0.1,
        "ssl": {
            "cafile": "test_cafile",
            "certfile": "test_certfile",
            "keyfile": "test_keyfile",
            "password": "test_password",
        },
    }

    def test_confluent_settings_contains_expected_values(self):
        expected_config = {
            "bootstrap.servers": "testserver:9092",
            "security.protocol": "SSL",
            "ssl.ca.location": "test_cafile",
            "ssl.certificate.location": "test_certfile",
            "ssl.key.location": "test_keyfile",
            "ssl.key.password": "test_password",
            "queue.buffering.max.messages": 100000,
            "compression.type": "none",
            "acks": -1,
            "linger.ms": 0.5,
        }
        kafka_input_cfg = self.object._confluent_settings
        assert kafka_input_cfg == expected_config

    @mock.patch("logprep.connector.confluent_kafka.output.Producer", return_value="The Producer")
    def test_producer_property_instanciates_kafka_producer(self, _):
        kafka_output = Factory.create({"test connector": self.CONFIG}, logger=self.logger)
        assert kafka_output._producer == "The Producer"

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        event = {"field": "content"}
        event_raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
        expected_call = mock.call(self.CONFIG.get("topic"), value=event_raw)
        self.object.store(event)
        kafka_producer.produce.assert_called()
        assert expected_call in kafka_producer.produce.mock_calls

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_custom_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        event = {"field": "content"}
        event_raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
        expected_call = mock.call(self.CONFIG.get("topic"), value=event_raw)
        self.object.store_custom(event, self.CONFIG.get("topic"))
        kafka_producer.produce.assert_called()
        assert expected_call in kafka_producer.produce.mock_calls

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_failed_calls_producer_produce(self, _):
        kafka_producer = self.object._producer
        event_received = {"field": "received"}
        event = {"field": "content"}
        error_message = "error message"
        self.object.store_failed(error_message, event_received, event)
        kafka_producer.produce.assert_called()
        mock_produce_call = kafka_producer.produce.mock_calls[0]
        assert self.CONFIG.get("error_topic") in mock_produce_call[1]
        assert "value" in mock_produce_call[2]
        mock_produce_call_value = mock_produce_call[2].get("value")
        mock_produce_call_value = json.loads(mock_produce_call_value.decode("utf8"))
        assert "error" in mock_produce_call_value
        assert "original" in mock_produce_call_value
        assert "processed" in mock_produce_call_value
        assert "timestamp" in mock_produce_call_value

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_custom_calls_producer_flush_on_buffererror(self, _):
        kafka_producer = self.object._producer
        kafka_producer.produce.side_effect = BufferError
        self.object.store_custom({"message": "does not matter"}, "doesnotcare")
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_failed_calls_producer_flush_on_buffererror(self, _):
        kafka_producer = self.object._producer
        kafka_producer.produce.side_effect = BufferError
        self.object.store_failed(
            "doesnotcare", {"message": "does not matter"}, {"message": "does not matter"}
        )
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_shut_down_calls_producer_flush(self, _):
        kafka_producer = self.object._producer
        self.object.shut_down()
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_create_confluent_settings_contains_expected_values2(self, _):
        self.object._producer.produce.side_effect = BaseException
        with pytest.raises(CriticalOutputError, match=r"Error storing output document:"):
            self.object.store({"message": "test message"})

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_counts_processed_events(self, _):  # pylint: disable=arguments-differ
        assert self.object.metrics.number_of_processed_events == 0
        self.object.store({"message": "my event message"})
        assert self.object.metrics.number_of_processed_events == 1

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_calls_batch_finished_callback(self, _):  # pylint: disable=arguments-differ
        self.object.input_connector = mock.MagicMock()
        self.object.store({"message": "my event message"})
        self.object.input_connector.batch_finished_callback.assert_called()
