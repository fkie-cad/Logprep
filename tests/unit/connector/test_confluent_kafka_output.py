# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use

import json
from unittest import mock
from logprep.connector.connector_factory import ConnectorFactory
from tests.unit.connector.base import BaseConnectorTestCase


class TestConfluentKafkaOutput(BaseConnectorTestCase):
    CONFIG = {
        "type": "confluentkafka_output",
        "bootstrapservers": ["testserver:9092"],
        "topic": "test_input_raw",
        "error_topic": "test_error_topic",
        "group": "test_producergroup",
        "auto_commit": False,
        "session_timeout": 654321,
        "enable_auto_offset_store": True,
        "offset_reset_policy": "latest",
        "flush_timeout": 0.1,
        "ssl": {
            "cafile": "test_cafile",
            "certfile": "test_certfile",
            "keyfile": "test_keyfile",
            "password": "test_password",
        },
    }

    @mock.patch("logprep.connector.confluent_kafka.output.Producer", return_value="The Producer")
    def test_producer_property_instanciates_kafka_producer(self, _):
        kafka_output = ConnectorFactory.create({"test connector": self.CONFIG}, logger=self.logger)
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
        assert self.CONFIG.get("error_topic") in mock_produce_call.args
        assert "value" in mock_produce_call.kwargs
        mock_produce_call_value = mock_produce_call.kwargs.get("value")
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
