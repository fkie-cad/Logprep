# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init

import json
from copy import deepcopy
from unittest import mock

import pytest
from confluent_kafka.error import KafkaException

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
        "flush_timeout": 0.1,
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
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    @mock.patch("logprep.connector.confluent_kafka.output.Producer", return_value="The Producer")
    def test_producer_property_instanciates_kafka_producer(self, _):
        kafka_output = Factory.create({"test connector": self.CONFIG})
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
    def test_store_custom_calls_producer_flush_on_buffererror(self, _):
        kafka_producer = self.object._producer
        kafka_producer.produce.side_effect = BufferError
        self.object.store_custom({"message": "does not matter"}, "doesnotcare")
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_shut_down_calls_producer_flush(self, _):
        kafka_producer = self.object._producer
        self.object.shut_down()
        kafka_producer.flush.assert_called()

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
            self.object.store({"message": "test message"})

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_counts_processed_events(self, _):  # pylint: disable=arguments-differ
        self.object.metrics.number_of_processed_events = 0
        self.object.store({"message": "my event message"})
        assert self.object.metrics.number_of_processed_events == 1

    def test_setup_raises_fatal_output_error_on_invalid_config(self):
        kafka_config = {"myconfig": "the config", "bootstrap.servers": "localhost:9092"}
        config = deepcopy(self.CONFIG)
        config.update({"kafka_config": kafka_config})
        connector = Factory.create({"test connector": config})
        with pytest.raises(FatalOutputError, match="No such configuration property"):
            connector.setup()

    def test_raises_value_error_if_mandatory_parameters_not_set(self):
        config = deepcopy(self.CONFIG)
        config.get("kafka_config").pop("bootstrap.servers")
        expected_error_message = r"keys are missing: {'bootstrap.servers'}"
        with pytest.raises(InvalidConfigurationError, match=expected_error_message):
            Factory.create({"test": config})

    def test_health_returns_true_if_no_error(self):
        self.object._admin = mock.MagicMock()
        metadata = mock.MagicMock()
        metadata.topics = [self.object._config.topic]
        self.object._admin.list_topics.return_value = metadata
        assert self.object.health()

    def test_health_returns_false_if_topic_not_present(self):
        self.object._admin = mock.MagicMock()
        metadata = mock.MagicMock()
        metadata.topics = ["not_the_topic"]
        self.object._admin.list_topics.return_value = metadata
        assert not self.object.health()

    def test_health_returns_false_on_kafka_exception(self):
        self.object._admin = mock.MagicMock()
        self.object._admin.list_topics.side_effect = KafkaException("test error")
        assert not self.object.health()

    def test_health_logs_error_on_kafka_exception(self):
        self.object._admin = mock.MagicMock()
        self.object._admin.list_topics.side_effect = KafkaException("test error")
        with mock.patch("logging.Logger.error") as mock_error:
            self.object.health()
        mock_error.assert_called()

    def test_health_counts_metrics_on_kafka_exception(self):
        self.object.metrics.number_of_errors = 0
        self.object._admin = mock.MagicMock()
        self.object._admin.list_topics.side_effect = KafkaException("test error")
        assert not self.object.health()
        assert self.object.metrics.number_of_errors == 1

    def test_shutdown_logs_and_counts_error_if_queue_not_fully_flushed(self):
        self.object.metrics.number_of_errors = 0
        self.object._producer = mock.MagicMock()
        self.object._producer.flush.return_value = 1
        with mock.patch("logging.Logger.error") as mock_error:
            self.object.shut_down()
        mock_error.assert_called()
        self.object.metrics.number_of_errors = 1

    def test_health_returns_bool(self):
        with mock.patch.object(self.object, "_admin"):
            super().test_health_returns_bool()

    @pytest.mark.parametrize(
        ["kafka_config_update", "expected_admin_client_config"],
        [
            ({}, {"bootstrap.servers": "localhost:9092"}),
            ({"statistics.foo": "bar"}, {"bootstrap.servers": "localhost:9092"}),
            (
                {"security.foo": "bar"},
                {"bootstrap.servers": "localhost:9092", "security.foo": "bar"},
            ),
            (
                {"ssl.foo": "bar"},
                {"bootstrap.servers": "localhost:9092", "ssl.foo": "bar"},
            ),
            (
                {"security.foo": "bar", "ssl.foo": "bar"},
                {"bootstrap.servers": "localhost:9092", "security.foo": "bar", "ssl.foo": "bar"},
            ),
        ],
    )
    @mock.patch("logprep.connector.confluent_kafka.output.AdminClient")
    def test_set_security_related_config_in_admin_client(
        self, admin_client, kafka_config_update, expected_admin_client_config
    ):
        new_kafka_config = deepcopy(self.CONFIG)
        new_kafka_config["kafka_config"].update(kafka_config_update)
        output_connector = Factory.create({"output_connector": new_kafka_config})
        _ = output_connector._admin
        admin_client.assert_called_with(expected_admin_client_config)
