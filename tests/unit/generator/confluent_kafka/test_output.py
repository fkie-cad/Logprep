# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from unittest import mock

import pytest
from prometheus_client import Counter, Gauge, Histogram

from logprep.abc.output import CriticalOutputError
from logprep.metrics.metrics import Metric
from tests.unit.connector.test_confluent_kafka_output import TestConfluentKafkaOutput


class TestConfluentKafkaGeneratorOutput(TestConfluentKafkaOutput):

    CONFIG = {
        "type": "confluentkafka_generator_output",
        "topic": "default",
        "flush_timeout": 0.1,
        "send_timeout": 1,
        "kafka_config": {
            "bootstrap.servers": "localhost:9092",
        },
    }

    expected_metrics = [
        "logprep_confluent_kafka_output_librdkafka_age",
        "logprep_confluent_kafka_output_librdkafka_msg_cnt",
        "logprep_confluent_kafka_output_librdkafka_msg_size",
        "logprep_confluent_kafka_output_librdkafka_msg_max",
        "logprep_confluent_kafka_output_librdkafka_msg_size_max",
        "logprep_confluent_kafka_output_librdkafka_tx",
        "logprep_confluent_kafka_output_librdkafka_tx_bytes",
        "logprep_confluent_kafka_output_librdkafka_rx",
        "logprep_confluent_kafka_output_librdkafka_rx_bytes",
        "logprep_confluent_kafka_output_librdkafka_txmsgs",
        "logprep_confluent_kafka_output_librdkafka_txmsg_bytes",
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_processed_batches",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        document = "default,test_payload"
        _, _, payload = document.partition(",")
        expected_call = mock.call(self.CONFIG.get("topic"), value=payload)
        self.object.store(document)
        kafka_producer.produce.assert_called()
        assert expected_call in kafka_producer.produce.mock_calls

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_custom_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        event = "{'field': 'content'}"
        expected_call = mock.call(self.CONFIG.get("topic"), value=event)
        self.object.store_custom(event, self.CONFIG.get("topic"))
        kafka_producer.produce.assert_called()
        assert expected_call in kafka_producer.produce.mock_calls

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_counts_processed_events(self, _):  # pylint: disable=arguments-differ
        self.object.metrics.number_of_processed_events = 0
        self.object.store("default,test_payload")
        assert self.object.metrics.number_of_processed_events == 1

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_raises_critical_output_on_any_exception(self, _):
        self.object._producer.produce.side_effect = [
            Exception("bad things happened"),
            None,
            None,
        ]
        with pytest.raises(
            CriticalOutputError,
            match=r"bad things happened",
        ):
            self.object.store("default,test_payload")

    def test_expected_metrics_attributes(self):
        for expected_metric in self.expected_metrics:
            metric_name = expected_metric.replace("logprep_confluent_kafka_output_", "")
            metric_name = metric_name.replace("logprep_", "")
            metric_attribute = getattr(self.object.metrics, metric_name)
            assert metric_attribute is not None
            assert isinstance(metric_attribute, Metric)

    def test_expected_metrics_attributes_are_initialized(self):
        for expected_metric in self.expected_metrics:
            metric_name = expected_metric.replace("logprep_confluent_kafka_output_", "")
            metric_name = metric_name.replace("logprep_", "")
            metric_attribute = getattr(self.object.metrics, metric_name)
            assert metric_attribute.tracker is not None
            possible_tracker_types = (Counter, Gauge, Histogram)
            assert isinstance(metric_attribute.tracker, possible_tracker_types)

    def test_store_updates_topic(self):
        assert self.object._config.topic == "default"
        self.object.store("test_topic,test_payload")
        assert self.object._config.topic == "test_topic"

    def test_store_counting_batches(self):
        self.object.store("test_topic,test_payload")
        assert self.object.metrics.processed_batches.tracker.collect()[0].samples[0].value == 1
        self.object.store("test_topic,test_payload")
        assert self.object.metrics.processed_batches.tracker.collect()[0].samples[0].value == 2

    def test_store_handles_empty_payload(self):
        with mock.patch(
            "logprep.generator.confluent_kafka.output.ConfluentKafkaGeneratorOutput.store_custom"
        ) as mock_store_custom:
            self.object.store("test_topic,")
            mock_store_custom.assert_called_once_with("", "test_topic")

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_statistic_calls_functions(self, _):
        self.object._producer.flush = mock.MagicMock()
        self.object._producer.poll = mock.MagicMock()
        _ = self.object.statistics
        self.object._producer.flush.assert_called_once_with(self.object._config.send_timeout)
        self.object._producer.poll.assert_called_once_with(self.object._config.send_timeout)
