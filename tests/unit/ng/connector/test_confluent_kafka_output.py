# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init

import json
import re
from copy import deepcopy
from functools import partial
from pathlib import Path
from socket import getfqdn
from unittest import mock

import pytest
from confluent_kafka import Producer
from confluent_kafka.error import KafkaException  # type: ignore

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.output import FatalOutputError
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.util.helper import get_dotted_field_value
from tests.unit.ng.connector.base import BaseOutputTestCase

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


@mock.patch("confluent_kafka.Consumer", new=mock.MagicMock())
@mock.patch("confluent_kafka.Producer", new=mock.MagicMock())
class TestConfluentKafkaOutput(BaseOutputTestCase):

    CONFIG = {
        "type": "ng_confluentkafka_output",
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

    def setup_method(self):
        super().setup_method()
        self.object._producer = mock.MagicMock()
        self.object._admin = mock.MagicMock()

    def test_client_id_is_set_to_hostname(self):
        self.object.setup()
        assert self.object._kafka_config.get("client.id") == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config})

    def test_error_callback_logs_error(self):
        self.object.metrics.number_of_errors = 0
        with mock.patch("logging.Logger.error") as mock_error:
            test_error = Exception("test error")
            self.object._error_callback(test_error)
            mock_error.assert_called()
            mock_error.assert_called_with("%s: %s", self.object.describe(), test_error)
        assert self.object.metrics.number_of_errors == 1

    def test_stats_callback_sets_metric_object_attributes(self):
        librdkafka_metrics = tuple(
            filter(lambda x: x.startswith("librdkafka"), self.expected_metrics)
        )
        for metric in librdkafka_metrics:
            setattr(self.object.metrics, metric, 0)

        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        stats_dict = json.loads(json_string)
        for metric in librdkafka_metrics:
            metric_name = metric.replace("librdkafka_", "").replace("cgrp_", "cgrp.")
            metric_value = get_dotted_field_value(stats_dict, metric_name)
            assert getattr(self.object.metrics, metric) == metric_value, metric

    def test_stats_set_age_metric_explicitly(self):
        self.object.metrics.librdkafka_age = 0
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        assert self.object.metrics.librdkafka_age == 1337

    def test_kafka_config_is_immutable(self):
        self.object.setup()
        with pytest.raises(TypeError):
            self.object._config.kafka_config["client.id"] = "test"

    def test_producer_property_instantiates_kafka_producer(self):
        kafka_output = Factory.create({"test connector": self.CONFIG})
        assert isinstance(kafka_output._producer, Producer)

    def test_store_sends_event_to_expected_topic(self):
        event_data = {"field": "content"}
        event = LogEvent(event_data, original=b"")
        with mock.patch.object(self.object, "_producer") as mock_producer:
            self.object.store(event)
        mock_producer.produce.assert_called()
        kwargs = mock_producer.produce.call_args[1]
        assert kwargs["topic"] == self.object._config.topic

    def test_store_custom_sends_event_to_expected_topic(self):
        event_data = {"field": "content"}
        event = LogEvent(event_data, original=b"")
        with mock.patch.object(self.object, "_producer") as mock_producer:
            self.object.store_custom(event, self.CONFIG.get("topic"))
        mock_producer.produce.assert_called()
        kwargs = mock_producer.produce.call_args[1]
        assert kwargs["topic"] == self.object._config.topic

    @mock.patch("logprep.ng.connector.confluent_kafka.output.Producer")
    def test_store_custom_calls_producer_flush_on_buffererror(self, _):
        kafka_producer = self.object._producer
        kafka_producer.produce.side_effect = BufferError
        event = LogEvent({"message": "does not matter"}, original=b"")
        self.object.store_custom(event, "does_not_care")
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.ng.connector.confluent_kafka.output.Producer")
    def test_shut_down_calls_producer_flush(self, _):
        kafka_producer = self.object._producer
        self.object.shut_down()
        kafka_producer.flush.assert_called()

    @mock.patch("logprep.ng.connector.confluent_kafka.output.Producer")
    def test_raises_critical_output_on_any_exception(self, _):
        self.object._producer.produce.side_effect = [
            Exception("bad things happened"),
            None,
            None,
        ]
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        self.object.store(event)
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

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
    @mock.patch("logprep.ng.connector.confluent_kafka.output.AdminClient")
    def test_set_security_related_config_in_admin_client(
        self, admin_client, kafka_config_update, expected_admin_client_config
    ):
        new_kafka_config = deepcopy(self.CONFIG)
        new_kafka_config["kafka_config"].update(kafka_config_update)
        output_connector = Factory.create({"output_connector": new_kafka_config})
        _ = output_connector._admin
        admin_client.assert_called_with(expected_admin_client_config)

    def test_store_changes_state_successful_path(self):
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store(event)
        assert event.state == EventStateType.STORED_IN_OUTPUT
        self.object.on_delivery(event, None, mock.MagicMock())
        assert event.state == expected_state

    def test_store_changes_state_failed_event_with_unsuccessful_path(self):
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store(event)
        assert event.state == EventStateType.STORED_IN_ERROR
        self.object.on_delivery(event, None, mock.MagicMock())
        assert event.state == expected_state

    def test_store_custom_changes_state_successful_path(self):
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store_custom(event, "stderr")
        assert event.state == EventStateType.STORED_IN_OUTPUT
        self.object.on_delivery(event, None, mock.MagicMock())
        assert event.state == expected_state, f"{state=}, {expected_state=}, {event.state=} "

    def test_store_custom_changes_state_failed_event_with_unsuccessful_path(self):
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store_custom(event, "stderr")
        assert event.state == EventStateType.STORED_IN_ERROR
        self.object.on_delivery(event, None, mock.MagicMock())
        assert event.state == expected_state, f"{state=}, {expected_state=}, {event.state=} "

    def test_store_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch.object(self.object, "_producer") as mock_producer:
            mock_producer.produce.side_effect = Exception("test error")
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch.object(self.object, "_producer") as mock_producer:
            mock_producer.produce.side_effect = Exception("test error")
            self.object.store_custom(event, "target_topic")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_store_handles_errors_failed_event(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch.object(self.object, "_producer") as mock_producer:
            mock_producer.produce.side_effect = Exception("test error")
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors_failed_event(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch.object(self.object, "_producer") as mock_producer:
            mock_producer.produce.side_effect = Exception("test error")
            self.object.store_custom(event, "target_topic")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_shutdown_flushes_output(self):
        with mock.patch(
            f"{self.object.__module__}.{self.object.__class__.__name__}.flush"
        ) as mock_flush:
            self.object.shut_down()
            mock_flush.assert_called_once()

    def test_on_delivery_successful(self, caplog):
        caplog.set_level("DEBUG")
        kafka_message = mock.MagicMock()
        kafka_message.topic = mock.MagicMock(return_value="test_topic")
        kafka_message.partition = mock.MagicMock(return_value=0)
        kafka_message.offset = mock.MagicMock(return_value=42)
        event = LogEvent(
            {"message": "test message"}, original=b"", state=EventStateType.STORED_IN_OUTPUT
        )
        self.object.on_delivery(event, None, kafka_message)
        assert len(event.errors) == 0
        assert event.state == EventStateType.DELIVERED
        assert re.search(
            r"Message delivered to 'test_topic' partition 0, offset 42",
            caplog.text,
        )

    def test_on_delivery_unsuccessful(self, caplog):
        caplog.set_level("ERROR")
        kafka_message = mock.MagicMock()
        kafka_error = mock.MagicMock()
        kafka_error.__str__ = mock.MagicMock(return_value="Kafka delivery error")
        event = LogEvent(
            {"message": "test message"}, original=b"", state=EventStateType.STORED_IN_OUTPUT
        )
        self.object.metrics.number_of_errors = 0
        self.object.on_delivery(event, kafka_error, kafka_message)
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED
        assert self.object.metrics.number_of_errors == 1
        assert re.search(
            r"Message delivery failed: Kafka delivery error",
            caplog.text,
        )

    @mock.patch("logprep.ng.connector.confluent_kafka.output.Producer")
    def test_produce_sets_on_delivery_callback(self, _):
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        event_data = self.object._encoder.encode(event.data)
        self.object._producer.produce = mock.MagicMock()
        self.object.store(event)
        kwargs = self.object._producer.produce.call_args[1]
        assert kwargs["value"] == event_data
        assert kwargs["topic"] == self.object._config.topic
        partial_function = kwargs["on_delivery"]
        assert isinstance(partial_function, partial)
        assert partial_function.func == self.object.on_delivery
        assert partial_function.args[0] == event

    def test_store_counts_processed_events(self):
        self.object.metrics.number_of_processed_events = 0
        event = LogEvent({"message": "my event message"}, original=b"")
        with mock.patch.object(self.object, "_producer"):
            self.object.store(event)
        assert self.object.metrics.number_of_processed_events == 1

    def test_flush_successfully_flushes_producer(self, caplog):
        caplog.set_level("INFO")
        with mock.patch.object(self.object, "_producer") as mock_producer:
            mock_producer.flush.return_value = 0
            self.object.flush()
        assert "0 messages remaining" in caplog.text
