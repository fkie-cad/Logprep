# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use

import json
import socket
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from logprep.abc.output import CriticalOutputError, FatalOutputError
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from tests.unit.connector.base import BaseOutputTestCase
from tests.unit.connector.test_confluent_kafka_common import (
    CommonConfluentKafkaTestCase,
)

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class TestConfluentKafkaOutput(BaseOutputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "confluentkafka_output",
        "topic": "test_input_raw",
        "error_topic": "test_error_topic",
        "flush_timeout": 0.1,
        "kafka_config": {
            "bootstrap.servers": "testserver:9092",
        },
    }

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
    def test_raises_critical_output_on_any_exception(self, _):
        self.object._producer.produce.side_effect = [
            BaseException("bad things happened"),
            None,
            None,
        ]
        self.object.store_failed = mock.MagicMock()
        with pytest.raises(
            CriticalOutputError,
            match=r"CriticalOutputError in ConfluentKafkaOutput"
            r" \(Test Instance Name\) - Kafka Output: testserver:9092: "
            r"Error storing output document -> bad things happened for event: "
            r"\{'message': 'test message'\}",
        ):
            self.object.store({"message": "test message"})
        self.object.store_failed.assert_called()

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

    def test_setup_raises_fatal_output_error_on_invalid_config(self):
        config = {"myconfig": "the config", "bootstrap.servers": "testserver:9092"}
        self.object._config.kafka_config = config
        with pytest.raises(FatalOutputError, match="No such configuration property"):
            self.object.setup()

    def test_metrics_expose_returns_data(self):
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        client_id = socket.getfqdn()
        # pylint: disable=line-too-long
        expected = {
            "logprep_connector_number_of_processed_events;direction:output,name:Test Instance Name,type:confluentkafka_output": 0.0,
            "logprep_connector_mean_processing_time_per_event;direction:output,name:Test Instance Name,type:confluentkafka_output": 0.0,
            "logprep_connector_number_of_warnings;direction:output,name:Test Instance Name,type:confluentkafka_output": 0.0,
            "logprep_connector_number_of_errors;direction:output,name:Test Instance Name,type:confluentkafka_output": 0.0,
            f"logprep_connector_librdkafka_producer_ts;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 5016483227792,
            f"logprep_connector_librdkafka_producer_time;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 1527060869,
            f"logprep_connector_librdkafka_producer_replyq;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 0,
            f"logprep_connector_librdkafka_producer_msg_cnt;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 22710,
            f"logprep_connector_librdkafka_producer_msg_size;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 704010,
            f"logprep_connector_librdkafka_producer_msg_max;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 500000,
            f"logprep_connector_librdkafka_producer_msg_size_max;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 1073741824,
            f"logprep_connector_librdkafka_producer_simple_cnt;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 0,
            f"logprep_connector_librdkafka_producer_metadata_cache_cnt;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 1,
            f"logprep_connector_librdkafka_producer_tx;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 631,
            f"logprep_connector_librdkafka_producer_tx_bytes;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 168584479,
            f"logprep_connector_librdkafka_producer_rx;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 631,
            f"logprep_connector_librdkafka_producer_rx_bytes;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 31084,
            f"logprep_connector_librdkafka_producer_txmsgs;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 4300753,
            f"logprep_connector_librdkafka_producer_txmsg_bytes;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 133323343,
            f"logprep_connector_librdkafka_producer_rxmsgs;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 0,
            f"logprep_connector_librdkafka_producer_rxmsg_bytes;direction:output,name:Test Instance Name,type:confluentkafka_output,client_id:{client_id}": 0,
        }
        # pylint: enable=line-too-long
        assert self.object.metrics.expose() == expected

    def test_raises_value_error_if_mandatory_parameters_not_set(self):
        config = deepcopy(self.CONFIG)
        config.get("kafka_config").pop("bootstrap.servers")
        expected_error_message = r"keys are missing: {'bootstrap.servers'}"
        with pytest.raises(InvalidConfigurationError, match=expected_error_message):
            Factory.create({"test": config}, logger=self.logger)
