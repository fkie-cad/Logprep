# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init

import re
import socket
from copy import deepcopy
from unittest import mock

import pytest
from confluent_kafka import (  # type: ignore
    OFFSET_BEGINNING,
    KafkaError,
    KafkaException,
)

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.input import (
    CriticalInputParsingError,
    FatalInputError,
    InputWarning,
)
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaMetadata
from tests.unit.connector.test_confluent_kafka_common import (
    CommonConfluentKafkaTestCase,
)
from tests.unit.ng.connector.base import BaseInputTestCase

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class TestConfluentKafkaInput(BaseInputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "ng_confluentkafka_input",
        "kafka_config": {"bootstrap.servers": "testserver:9092", "group.id": "testgroup"},
        "topic": "test_input_raw",
        "health_timeout": 0.1,
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
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_get_next_returns_none_if_no_records(self, mock_consumer_cls):
        mock_consumer = mock.MagicMock()
        mock_consumer.poll.return_value = None
        mock_consumer_cls.return_value = mock_consumer

        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})
        kafka_input._wait_for_health = mock.MagicMock()
        kafka_input.setup()

        event = kafka_input.get_next(1)
        assert event is None

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(
        self, mock_consumer_cls
    ):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})
        kafka_input._wait_for_health = mock.MagicMock()
        kafka_input.setup()

        mock_kafka_message = mock.MagicMock()
        mock_kafka_message.error.return_value = KafkaError(
            error=3,
            reason="Subscribed topic not available: (Test Instance Name) : "
            "Broker: Unknown topic or partition",
            fatal=False,
            retriable=False,
            txn_requires_abort=False,
        )

        mock_consumer = mock.MagicMock()
        mock_consumer.poll.return_value = mock_kafka_message
        mock_consumer_cls.return_value = mock_consumer

        assert kafka_input.get_next(1) is None

        expected_error_message = "A confluent-kafka record contains an error code"
        self.check_input_registered_failed_event_with_message(
            connector=kafka_input,
            expected_error_message=expected_error_message,
        )

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_shut_down_calls_consumer_close(self, _):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})

        kafka_consumer = kafka_input._consumer
        kafka_input.shut_down()
        kafka_consumer.close.assert_called()

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_calls_store_offsets(self, _):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})

        kafka_consumer = kafka_input._consumer
        message = "test message"
        kafka_input._last_valid_record = message
        kafka_input.batch_finished_callback()
        kafka_consumer.store_offsets.assert_called()
        kafka_consumer.store_offsets.assert_called_with(message=message)

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_does_not_call_store_offsets(self, _):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})

        kafka_consumer = kafka_input._consumer
        kafka_input._last_valid_record = None
        kafka_input.batch_finished_callback()
        kafka_consumer.store_offsets.assert_not_called()

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_raises_input_warning_on_kafka_exception(self, _):
        input_config = deepcopy(self.CONFIG)
        kafka_input = Factory.create({"test": input_config})

        kafka_consumer = kafka_input._consumer
        return_sequence = [KafkaException("test error"), None]

        def raise_generator(return_sequence):
            return list(reversed(return_sequence)).pop()

        kafka_consumer.store_offsets.side_effect = raise_generator(return_sequence)
        kafka_input._last_valid_record = {0: "message"}
        with pytest.raises(InputWarning):
            kafka_input.batch_finished_callback()

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_error_if_not_a_dict(self, mock_consumer):
        input_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test": input_config})
        connector._wait_for_health = mock.MagicMock()
        connector.setup()

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")

        mock_consumer.poll = mock.MagicMock(return_value=mock_record)

        assert connector.get_next(1) is None

        expected_error_message = "A confluent-kafka record contains an error code"
        self.check_input_registered_failed_event_with_message(
            connector=connector,
            expected_error_message=expected_error_message,
        )

        connector.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_error_if_invalid_json(self, mock_consumer):
        input_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test": input_config})
        connector._wait_for_health = mock.MagicMock()
        connector.setup()

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.value.return_value = "I'm not valid json".encode("utf8")

        mock_consumer.poll = mock.MagicMock(return_value=mock_record)

        assert connector.get_next(1) is None

        expected_error_message = "A confluent-kafka record contains an error code"
        self.check_input_registered_failed_event_with_message(
            connector=connector,
            expected_error_message=expected_error_message,
        )

        connector.shut_down()

    def test_get_event_returns_event_and_raw_event(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()

            mock_record.error.return_value = None
            mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
            mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
            mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
            mock_record.partition.return_value = 1
            mock_record.offset.return_value = 42

            mock_consumer.poll = mock.MagicMock(return_value=mock_record)

            event, raw_event, metadata = self.object._get_event(0.001)
            assert event == {"element": "in list"}
            assert raw_event == '{"element":"in list"}'.encode("utf8")
            assert metadata == ConfluentKafkaMetadata(partition=1, offset=42)

    def test_get_raw_event_is_callable(self):  # pylint: disable=arguments-differ
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            # should be overwritten if reimplemented
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None
            mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")

            mock_consumer.poll = mock.MagicMock(return_value=mock_record)

            result = self.object._get_raw_event(0.001)

            assert result

    def test_get_event_raises_exception_if_input_invalid_json(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None
            mock_record.value.return_value = '{"invalid_json"}'.encode("utf8")

            mock_consumer.poll = mock.MagicMock(return_value=mock_record)

            with pytest.raises(
                CriticalInputParsingError,
                match=(
                    r"Input record value is not a valid json string ->"
                    r" event was written to error output if configured"
                ),
            ) as error:
                self.object._get_event(0.001)
            assert error.value.raw_input == b'{"invalid_json"}'

    def test_get_event_raises_exception_if_input_not_utf(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None

            mock_record.value.return_value = '{"not_utf-8": \xfc}'.encode("cp1252")

            mock_consumer.poll = mock.MagicMock(return_value=mock_record)

            with pytest.raises(
                CriticalInputParsingError,
                match=(
                    r"Input record value is not \'utf-8\' encoded ->"
                    r" event was written to error output if configured"
                ),
            ) as error:
                self.object._get_event(0.001)
            assert error.value.raw_input == "b'{\"not_utf-8\": \\xfc}'"

    def test_setup_raises_fatal_input_error_on_invalid_config(self):
        kafka_config = {
            "bootstrap.servers": "testinstance:9092",
            "group.id": "sapsal",
            "myconfig": "the config",
        }
        config = deepcopy(self.CONFIG)
        config["kafka_config"] = kafka_config
        connector = Factory.create({"test": config})
        with pytest.raises(FatalInputError, match="No such configuration property"):
            connector.setup()

    def test_get_next_raises_critical_input_parsing_error(self):
        input_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test": input_config})
        connector._wait_for_health = mock.MagicMock()
        connector.setup()

        return_value = b'{"invalid": "json'
        mock_message = mock.MagicMock()
        mock_message.value.return_value = return_value

        with mock.patch.object(connector, "_get_raw_event", return_value=mock_message):
            assert connector.get_next(1) is None

            self.check_input_registered_failed_event_with_message(
                connector=connector,
                expected_error_message="Input record value is not a valid json string",
            )

    def test_commit_callback_raises_warning_error_and_counts_failures(self):
        with pytest.raises(InputWarning, match="Could not commit offsets"):
            self.object._commit_callback(Exception, ["topic_partition"])
            assert self.object._commit_failures == 1

    def test_commit_callback_counts_commit_success(self):
        self.object.metrics.commit_success = 0
        self.object._commit_callback(None, [mock.MagicMock()])
        assert self.object.metrics.commit_success == 1

    def test_commit_callback_sets_committed_offsets(self):
        mock_add = mock.MagicMock()
        self.object.metrics.committed_offsets.add_with_labels = mock_add
        topic_partition = mock.MagicMock()
        topic_partition.partition = 99
        topic_partition.offset = 666
        self.object._commit_callback(None, [topic_partition])
        call_args = 666, {"description": "topic: test_input_raw - partition: 99"}
        mock_add.assert_called_with(*call_args)

    def test_default_config_is_injected(self):
        with mock.patch(
            "logprep.ng.connector.confluent_kafka.input.Consumer", autospec=True
        ) as mock_consumer:
            input_config = deepcopy(self.CONFIG)
            kafka_input = Factory.create({"test": input_config})

            _ = kafka_input._consumer

            mock_consumer.assert_called()

            called_args = mock_consumer.call_args[0][0]
            assert called_args.get("bootstrap.servers") == "testserver:9092"
            assert called_args.get("enable.auto.offset.store") == "false"

            kafka_input.shut_down()

    def test_auto_offset_store_and_auto_commit_are_managed_by_connector(self):
        with mock.patch(
            "logprep.ng.connector.confluent_kafka.input.Consumer", autospec=True
        ) as mock_consumer:
            config = deepcopy(self.CONFIG)
            config["kafka_config"] |= {
                "enable.auto.offset.store": "true",
                "enable.auto.commit": "false",
            }
            kafka_input = Factory.create({"test": config})

            _ = kafka_input._consumer

            mock_consumer.assert_called()

            injected_config = mock_consumer.call_args[0][0]
            assert injected_config.get("enable.auto.offset.store") == "false"
            assert injected_config.get("enable.auto.commit") == "true"

            kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.AdminClient")
    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_client_id_can_be_overwritten(self, mock_consumer, mock_admin):
        input_config = deepcopy(self.CONFIG)
        input_config["kafka_config"]["client.id"] = "thisclientid"
        kafka_input = Factory.create({"test": input_config})
        kafka_input._wait_for_health = mock.MagicMock()
        metadata = mock.MagicMock()
        metadata.topics = [kafka_input._config.topic]
        mock_admin.list_topics.return_value = metadata
        kafka_input.setup()

        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("client.id") == "thisclientid"
        assert not mock_consumer.call_args[0][0].get("client.id") == socket.getfqdn()

        kafka_input.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.AdminClient")
    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_statistics_interval_can_be_overwritten(self, mock_consumer, mock_admin):
        input_config = deepcopy(self.CONFIG)
        input_config["kafka_config"]["statistics.interval.ms"] = "999999999"
        kafka_input = Factory.create({"test": input_config})
        kafka_input._wait_for_health = mock.MagicMock()
        metadata = mock.MagicMock()
        metadata.topics = [kafka_input._config.topic]
        mock_admin.list_topics.return_value = metadata
        kafka_input.setup()

        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("statistics.interval.ms") == "999999999"

        kafka_input.shut_down()

    def test_raises_fatal_input_error_if_poll_raises_runtime_error(self):
        input_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test": input_config})
        connector._wait_for_health = mock.MagicMock()
        connector.setup()

        with mock.patch.object(connector, "_consumer") as mock_consumer:
            mock_consumer.poll.side_effect = RuntimeError("test error")

            with pytest.raises(FatalInputError, match="test error"):
                connector.get_next(0.01)

    def test_raises_value_error_if_mandatory_parameters_not_set(self):
        config = deepcopy(self.CONFIG)
        config.get("kafka_config").pop("bootstrap.servers")
        config.get("kafka_config").pop("group.id")
        expected_error_message = r"keys are missing: {'(bootstrap.servers|group.id)', '(bootstrap.servers|group.id)'}"  # pylint: disable=line-too-long
        with pytest.raises(InvalidConfigurationError, match=expected_error_message):
            Factory.create({"test": config})

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

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_lost_callback_counts_warnings_and_logs(self, _):
        self.object.metrics.number_of_warnings = 0
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.object._lost_callback(mock_partitions)
        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings == 1

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    def test_commit_callback_sets_offset_to_0_for_special_offsets(self, _):
        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        mock_partitions[0].offset = OFFSET_BEGINNING
        self.object._commit_callback(None, mock_partitions)
        expected_labels = {
            "description": f"topic: test_input_raw - partition: {mock_partitions[0].partition}"
        }
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(0, expected_labels)

    @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
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

    def test_revoke_callback_logs_warning_and_counts(self):
        self.object.metrics.number_of_warnings = 0
        self.object.output_connector = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.object._revoke_callback(None, mock_partitions)
        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings == 1

    def test_revoke_callback_calls_batch_finished_callback(self):
        self.object.output_connector = mock.MagicMock()
        self.object.batch_finished_callback = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        self.object._revoke_callback(None, mock_partitions)
        self.object.batch_finished_callback.assert_called()

    def test_revoke_callback_logs_error_if_consumer_closed(self, caplog):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.memberid = mock.MagicMock()
            mock_consumer.memberid.side_effect = RuntimeError("Consumer is closed")
            mock_partitions = [mock.MagicMock()]
            self.object._revoke_callback(None, mock_partitions)
            assert re.search(r"ERROR.*Consumer is closed", caplog.text)

    @mock.patch("logprep.ng.connector.confluent_kafka.input.AdminClient")
    def test_health_returns_true_if_no_error(self, mock_admin_class):
        mock_admin = mock.MagicMock()
        mock_admin.list_topics.return_value.topics = ["test-topic"]
        mock_admin_class.return_value = mock_admin

        input_config = deepcopy(self.CONFIG)
        input_config["topic"] = "test-topic"
        connector = Factory.create({"test": input_config})
        connector._wait_for_health = mock.MagicMock()
        connector.setup()

        assert connector.health()

        connector.shut_down()

    @mock.patch("logprep.ng.connector.confluent_kafka.input.AdminClient")
    def test_health_returns_false_if_topic_not_present(self, mock_admin):
        metadata = mock.MagicMock()
        metadata.topics = ["not_the_topic"]
        mock_admin.list_topics.return_value = metadata
        assert not self.object.health()

    def test_health_returns_false_on_kafka_exception(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.list_topics.side_effect = KafkaException("test error")
            assert not self.object.health()

    def test_health_logs_error_on_kafka_exception(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.list_topics.side_effect = KafkaException("test error")

            with mock.patch("logging.Logger.error") as mock_error:
                self.object.health()

            mock_error.assert_called()

    def test_health_counts_metrics_on_kafka_exception(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.list_topics.side_effect = KafkaException("test error")

            self.object.metrics.number_of_errors = 0

            assert not self.object.health()
            assert self.object.metrics.number_of_errors == 1

    @pytest.mark.parametrize(
        ["kafka_config_update", "expected_admin_client_config"],
        [
            ({}, {"bootstrap.servers": "testserver:9092"}),
            ({"statistics.foo": "bar"}, {"bootstrap.servers": "testserver:9092"}),
            (
                {"security.foo": "bar"},
                {"bootstrap.servers": "testserver:9092", "security.foo": "bar"},
            ),
            (
                {"ssl.foo": "bar"},
                {"bootstrap.servers": "testserver:9092", "ssl.foo": "bar"},
            ),
            (
                {"security.foo": "bar", "ssl.foo": "bar"},
                {"bootstrap.servers": "testserver:9092", "security.foo": "bar", "ssl.foo": "bar"},
            ),
        ],
    )
    @mock.patch("logprep.ng.connector.confluent_kafka.input.AdminClient")
    def test_set_security_related_config_in_admin_client(
        self, admin_client, kafka_config_update, expected_admin_client_config
    ):
        new_kafka_config = deepcopy(self.CONFIG)
        new_kafka_config["kafka_config"].update(kafka_config_update)
        input_connector = Factory.create({"input_connector": new_kafka_config})
        _ = input_connector._admin
        admin_client.assert_called_with(expected_admin_client_config)
