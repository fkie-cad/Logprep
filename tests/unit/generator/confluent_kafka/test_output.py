# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


import json
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
        "send_timeout": 0,
        "kafka_config": {
            "bootstrap.servers": "localhost:9092",
        },
    }

    # expected_metrics = [
    #     "logprep_confluent_kafka_generator_output_librdkafka_age",
    #     "logprep_confluent_kafka_generator_output_librdkafka_msg_cnt",
    #     "logprep_confluent_kafka_generator_output_librdkafka_msg_size",
    #     "logprep_confluent_kafka_generator_output_librdkafka_msg_max",
    #     "logprep_confluent_kafka_generator_output_librdkafka_msg_size_max",
    #     "logprep_confluent_kafka_generator_output_librdkafka_tx",
    #     "logprep_confluent_kafka_generator_output_librdkafka_tx_bytes",
    #     "logprep_confluent_kafka_generator_output_librdkafka_rx",
    #     "logprep_confluent_kafka_generator_output_librdkafka_rx_bytes",
    #     "logprep_confluent_kafka_generator_output_librdkafka_txmsgs",
    #     "logprep_confluent_kafka_generator_output_librdkafka_txmsg_bytes",
    #     "logprep_processing_time_per_event",
    #     "logprep_number_of_processed_events",
    #     "logprep_processed_batches",
    #     "logprep_number_of_warnings",
    #     "logprep_number_of_errors",
    # ]

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

    def test_test(self):
        assert 5 == 5

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        document = "default,test_payload"
        topic, _, payload = document.partition(",")
        event_raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        expected_call = mock.call(self.CONFIG.get("topic"), value=event_raw)
        self.object.store(document)
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
            possibile_tracker_types = (Counter, Gauge, Histogram)
            assert isinstance(metric_attribute.tracker, possibile_tracker_types)

    # self.output = Factory.create(output_config)

    # self.output.metrics = MagicMock()
    # self.output.metrics.processed_batches = 0
    # self.output.store_custom = MagicMock()

    # def test_store_calls_store_custom(self):
    #     self.output.store("test_topic,test_payload")
    #     self.output.store_custom.assert_called_once_with("test_payload", "test_topic")

    # def test_store_updates_topic(self):
    #     assert self.output._config.topic == "producer"
    #     self.output.store("test_topic,test_payload")
    #     assert self.output._config.topic == "test_topic"

    # def test_store_counting_batches(self):
    #     self.output.store("test_topic,test_payload")
    #     assert self.output.metrics.processed_batches == 1
    #     self.output.store("test_topic,test_payload")
    #     assert self.output.metrics.processed_batches == 2

    # def test_store_handles_empty_payload(self):
    #     self.output.store("test_topic,")
    #     self.output.store_custom.assert_called_once_with("", "test_topic")

    # def test_store_handles_missing_comma(self):
    #     self.output.store("test_topic_only")
    #     self.output.store_custom.assert_called_once_with("", "test_topic_only")

    # def test_store_calles_super_store(self):
    #     with patch.object(ConfluentKafkaOutput, "store", MagicMock()) as mock_store:
    #         self.output.store({"test_field": "test_value"})
    #         mock_store.assert_called_once_with({"test_field": "test_value"})

    # @pytest.mark.parametrize(
    #     "topic, expected",
    #     [
    #         ("valid_topic", True),
    #         ("valid-topic-123", True),
    #         ("valid.topic_123", True),
    #         ("", False),
    #         ("..", False),
    #         (".", False),
    #         (
    #             "this_is_a_very_long_topic_name_that_exceeds_the_maximum_length_limit_of_249_characters_"
    #             + "a" * 200,
    #             False,
    #         ),
    #         ("invalid topic", False),
    #         ("invalid#topic", False),
    #         ("invalid@topic", False),
    #     ],
    # )
    # def test_is_valid_kafka_topic(self, topic, expected):
    #     assert self.output._is_valid_kafka_topic(topic) == expected

    # @pytest.mark.parametrize(
    #     "targets, should_raise, expected_faulty",
    #     [
    #         (["valid", "another_valid"], False, []),
    #         (["/invalid", "valid"], True, ["/invalid"]),
    #         (["/invalid", "invalid#"], True, ["/invalid", "invalid#"]),
    #     ],
    # )
    # def test_validate(self, targets, should_raise, expected_faulty):
    #     if should_raise:
    #         with pytest.raises(ValueError) as exc_info:
    #             self.output.validate(targets)
    #         assert str(exc_info.value) == f"Invalid Kafka topic names: {expected_faulty}"
    #     else:
    #         self.output.validate(targets)
