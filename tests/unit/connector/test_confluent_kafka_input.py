# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
import socket
from copy import deepcopy
from unittest import mock

import pytest
from confluent_kafka import OFFSET_BEGINNING, KafkaException

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    InputWarning,
)
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from tests.unit.connector.base import BaseInputTestCase
from tests.unit.connector.test_confluent_kafka_common import (
    CommonConfluentKafkaTestCase,
)

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class TestConfluentKafkaInput(BaseInputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "confluentkafka_input",
        "kafka_config": {"bootstrap.servers": "testserver:9092", "group.id": "testgroup"},
        "topic": "test_input_raw",
    }

    expected_metrics = [
        "logprep_confluent_kafka_input_commit_failures",
        "logprep_confluent_kafka_input_commit_success",
        "logprep_confluent_kafka_input_current_offsets",
        "logprep_confluent_kafka_input_committed_offsets",
        "logprep_confluent_kafka_input_librdkafka_age",
        "logprep_confluent_kafka_input_librdkafka_rx",
        "logprep_confluent_kafka_input_librdkafka_rx_bytes",
        "logprep_confluent_kafka_input_librdkafka_rxmsgs",
        "logprep_confluent_kafka_input_librdkafka_rxmsg_bytes",
        "logprep_confluent_kafka_input_librdkafka_cgrp_stateage",
        "logprep_confluent_kafka_input_librdkafka_cgrp_rebalance_age",
        "logprep_confluent_kafka_input_librdkafka_cgrp_rebalance_cnt",
        "logprep_confluent_kafka_input_librdkafka_cgrp_assignment_size",
        "logprep_confluent_kafka_input_librdkafka_replyq",
        "logprep_confluent_kafka_input_librdkafka_tx",
        "logprep_confluent_kafka_input_librdkafka_tx_bytes",
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_failed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_returns_none_if_no_records(self, _):
        self.object._consumer.poll = mock.MagicMock(return_value=None)
        event, non_critical_error_msg = self.object.get_next(1)
        assert event is None
        assert non_critical_error_msg is None

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock(return_value="An arbitrary confluent-kafka error")
        mock_record.value = mock.MagicMock(return_value=None)
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        with pytest.raises(
            CriticalInputError,
            match=(
                r"CriticalInputError in ConfluentKafkaInput \(Test Instance Name\) - "
                r"Kafka Input: testserver:9092: "
                r"A confluent-kafka record contains an error code -> "
                r"An arbitrary confluent-kafka error"
            ),
        ):
            _, _ = self.object.get_next(1)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_shut_down_calls_consumer_close(self, _):
        kafka_consumer = self.object._consumer
        self.object.shut_down()
        kafka_consumer.close.assert_called()

    @pytest.mark.parametrize(
        "settings,handlers",
        [
            (
                {"enable.auto.offset.store": "false", "enable.auto.commit": "true"},
                ("store_offsets",),
            ),
            (
                {"enable.auto.offset.store": "false", "enable.auto.commit": "false"},
                ("store_offsets", "commit"),
            ),
            ({"enable.auto.offset.store": "true", "enable.auto.commit": "false"}, None),
            ({"enable.auto.offset.store": "true", "enable.auto.commit": "true"}, None),
        ],
    )
    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_calls_offsets_handler_for_setting(self, _, settings, handlers):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config}, logger=self.logger)
        kafka_input._config.kafka_config.update(settings)
        kafka_consumer = kafka_input._consumer
        message = "test message"
        kafka_input._last_valid_records = {0: message}
        kafka_input.batch_finished_callback()
        if handlers is None:
            assert kafka_consumer.commit.call_count == 0
            assert kafka_consumer.store_offsets.call_count == 0
        else:
            for handler in handlers:
                getattr(kafka_consumer, handler).assert_called()
                getattr(kafka_consumer, handler).assert_called_with(message=message)

    @pytest.mark.parametrize(
        "settings,handler",
        [
            ({"enable.auto.offset.store": "false", "enable.auto.commit": "true"}, "store_offsets"),
            ({"enable.auto.offset.store": "false", "enable.auto.commit": "false"}, "commit"),
        ],
    )
    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_raises_input_warning_on_kafka_exception(
        self, _, settings, handler
    ):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config}, logger=self.logger)
        kafka_input._config.kafka_config.update(settings)
        kafka_consumer = kafka_input._consumer
        return_sequence = [KafkaException("test error"), None]

        def raise_generator(return_sequence):
            return list(reversed(return_sequence)).pop()

        getattr(kafka_consumer, handler).side_effect = raise_generator(return_sequence)
        kafka_input._last_valid_records = {0: "message"}
        with pytest.raises(InputWarning):
            kafka_input.batch_finished_callback()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_error_if_not_a_dict(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")
        with pytest.raises(CriticalInputError, match=r"not a dict"):
            self.object.get_next(1)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_error_if_unvalid_json(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = "I'm not valid json".encode("utf8")
        with pytest.raises(CriticalInputError, match=r"not a valid json"):
            self.object.get_next(1)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_event_returns_event_and_raw_event(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
        event, raw_event = self.object._get_event(0.001)
        assert event == {"element": "in list"}
        assert raw_event == '{"element":"in list"}'.encode("utf8")

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_raw_event_is_callable(self, _):  # pylint: disable=arguments-differ
        # should be overwritten if reimplemented
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
        result = self.object._get_raw_event(0.001)
        assert result

    def test_setup_raises_fatal_input_error_on_invalid_config(self):
        config = {
            "bootstrap.servers": "testinstance:9092",
            "group.id": "sapsal",
            "myconfig": "the config",
        }
        self.object._config.kafka_config = config
        with pytest.raises(FatalInputError, match="No such configuration property"):
            self.object.setup()

    def test_get_next_raises_critical_input_parsing_error(self):
        return_value = b'{"invalid": "json'
        self.object._get_raw_event = mock.MagicMock(return_value=return_value)
        with pytest.raises(CriticalInputParsingError, match="is not a valid json"):
            self.object.get_next(0.01)

    def test_commit_callback_raises_warning_error_and_counts_failures(self):
        with pytest.raises(InputWarning, match="Could not commit offsets"):
            self.object._commit_callback(BaseException, ["topic_partition"])
            assert self.object._commit_failures == 1

    def test_commit_callback_counts_commit_success(self):
        self.object.metrics.commit_success = 0
        self.object._commit_callback(None, [mock.MagicMock()])
        assert self.object.metrics.commit_success == 1

    def test_commit_callback_sets_committed_offsets(self):
        mock_add = mock.MagicMock()
        self.object.metrics.committed_offsets.add_with_labels = mock_add
        topic_partion = mock.MagicMock()
        topic_partion.partition = 99
        topic_partion.offset = 666
        self.object._commit_callback(None, [topic_partion])
        call_args = 666, {"description": "topic: test_input_raw - partition: 99"}
        mock_add.assert_called_with(*call_args)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_default_config_is_injected(self, mock_consumer):
        injected_config = {
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "client.id": socket.getfqdn(),
            "auto.offset.reset": "earliest",
            "session.timeout.ms": "6000",
            "statistics.interval.ms": "30000",
            "bootstrap.servers": "testserver:9092",
            "group.id": "testgroup",
            "logger": self.object._logger,
            "on_commit": self.object._commit_callback,
            "stats_cb": self.object._stats_callback,
            "error_cb": self.object._error_callback,
        }
        _ = self.object._consumer
        mock_consumer.assert_called_with(injected_config)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_client_id_can_be_overwritten(self, mock_consumer):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config}, logger=self.logger)
        kafka_input._config.kafka_config["client.id"] = "thisclientid"
        kafka_input.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("client.id") == "thisclientid"
        assert not mock_consumer.call_args[0][0].get("client.id") == socket.getfqdn()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_statistics_interval_can_be_overwritten(self, mock_consumer):
        kafka_input = Factory.create({"test": self.CONFIG}, logger=self.logger)
        kafka_input._config.kafka_config["statistics.interval.ms"] = "999999999"
        kafka_input.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("statistics.interval.ms") == "999999999"

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_raises_fatal_input_error_if_poll_raises_runtime_error(self, _):
        self.object._consumer.poll.side_effect = RuntimeError("test error")
        with pytest.raises(FatalInputError, match="test error"):
            self.object.get_next(0.01)

    def test_raises_value_error_if_mandatory_parameters_not_set(self):
        config = deepcopy(self.CONFIG)
        config.get("kafka_config").pop("bootstrap.servers")
        config.get("kafka_config").pop("group.id")
        expected_error_message = r"keys are missing: {'(bootstrap.servers|group.id)', '(bootstrap.servers|group.id)'}"  # pylint: disable=line-too-long
        with pytest.raises(InvalidConfigurationError, match=expected_error_message):
            Factory.create({"test": config}, logger=self.logger)

    @pytest.mark.parametrize(
        "metric_name",
        [
            "current_offsets",
            "committed_offsets",
        ],
    )
    def test_offset_metrics_not_initialized_with_default_label_values(self, metric_name):
        metric = getattr(self.object.metrics, metric_name)
        metric_object = metric.tracker.collect()[0]
        assert len(metric_object.samples) == 0

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_lost_callback_reassings_to_partitions(self, mock_consumer):
        mock_partitions = [mock.MagicMock()]
        self.object._consumer.assign = mock.MagicMock()
        self.object._lost_callback(mock_consumer, mock_partitions)
        self.object._consumer.assign.assert_called_with(mock_partitions)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_lost_callback_counts_warnings(self, mock_consumer):
        self.object.metrics.number_of_warnings = 0
        mock_partitions = [mock.MagicMock()]
        self.object._lost_callback(mock_consumer, mock_partitions)
        assert self.object.metrics.number_of_warnings == 1

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_commit_callback_sets_offset_to_0_for_special_offsets(self, _):
        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        mock_partitions[0].offset = OFFSET_BEGINNING
        self.object._commit_callback(None, mock_partitions)
        expected_labels = {
            "description": f"topic: test_input_raw - partition: {mock_partitions[0].partition}"
        }
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(0, expected_labels)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_assign_callback_sets_offsets_and_logs_info(self, mock_consumer):
        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        self.object.metrics.current_offsets.add_with_labels = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        mock_partitions[0].offset = OFFSET_BEGINNING
        with mock.patch("logging.Logger.info") as mock_info:
            self.object._assign_callback(mock_consumer, mock_partitions)
        expected_labels = {
            "description": f"topic: test_input_raw - partition: {mock_partitions[0].partition}"
        }
        mock_info.assert_called()
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(0, expected_labels)
        self.object.metrics.current_offsets.add_with_labels.assert_called_with(0, expected_labels)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_revoke_callback_logs_warning_and_counts(self, mock_consumer):
        self.object.metrics.number_of_warnings = 0
        self.object.output_connector = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.object._revoke_callback(mock_consumer, mock_partitions)
        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings == 1

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_revoke_callback_writes_output_backlog_and_calls_batch_finished_callback(
        self, mock_consumer
    ):
        self.object.output_connector = mock.MagicMock()
        self.object.batch_finished_callback = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        self.object._revoke_callback(mock_consumer, mock_partitions)
        self.object.output_connector._write_backlog.assert_called()
        self.object.batch_finished_callback.assert_called()
