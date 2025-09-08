# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
import builtins
import json
import os
import re
import socket
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from confluent_kafka import OFFSET_BEGINNING, KafkaError, KafkaException  # type: ignore

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    InputWarning,
)
from logprep.connector.confluent_kafka.input import logger
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.util.helper import get_dotted_field_value
from tests.unit.connector.base import BaseInputTestCase

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


@mock.patch("confluent_kafka.Consumer", new=mock.MagicMock())
@mock.patch("confluent_kafka.Producer", new=mock.MagicMock())
class TestConfluentKafkaInput(BaseInputTestCase):
    CONFIG = {
        "type": "confluentkafka_input",
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

    def setup_method(self):
        super().setup_method()
        self.object._consumer = mock.MagicMock()
        self.object._admin = mock.MagicMock()

    def test_client_id_is_set_to_hostname(self):
        self.object.setup()
        assert self.object._kafka_config.get("client.id") == socket.getfqdn()

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

    def test_stats_callback_sets_metric_objetc_attributes(self):
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

    def test_get_next_returns_none_if_no_records(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.poll.return_value = None
            event = self.object.get_next(1)
            assert event is None

    def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error = mock.MagicMock(
                return_value=KafkaError(
                    error=3,
                    reason="Subscribed topic not available: (Test Instance Name) : "
                    "Broker: Unknown topic or partition",
                    fatal=False,
                    retriable=False,
                    txn_requires_abort=False,
                )
            )
            mock_consumer.poll.return_value = mock_record

            with pytest.raises(
                CriticalInputError,
                match=(
                    r"CriticalInputError in ConfluentKafkaInput \(Test Instance Name\) - "
                    r"Kafka Input: testserver:9092: "
                    r"A confluent-kafka record contains an error code -> "
                    r"event was written to error output if configured"
                ),
            ):
                _ = self.object.get_next(1)

    def test_shut_down_calls_consumer_close(
        self,
    ):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:

            # When the first "with" block ends, it tries to delete the mocked _consumer from self.object.
            # But self.object.shut_down() removes all attributes from self.object, so this causes AttributeError.
            # To prevent that, we mock builtins.hasattr so shut_down doesn’t try to delete attributes in this test.
            with mock.patch.object(builtins, "hasattr", return_value=False):
                self.object.shut_down()

            mock_consumer.close.assert_called()

    def test_batch_finished_callback_calls_store_offsets(self):
        message = "test message"

        with (
            mock.patch.object(self.object, "_consumer") as mock_consumer,
            mock.patch.object(self.object, "_last_valid_record", new=message),
        ):
            self.object.batch_finished_callback()

            mock_consumer.store_offsets.assert_called()
            mock_consumer.store_offsets.assert_called_with(message=message)

    def test_batch_finished_callback_does_not_call_store_offsets(self):
        with (
            mock.patch.object(self.object, "_consumer") as mock_consumer,
            mock.patch.object(self.object, "_last_valid_record", new=None),
        ):
            self.object.batch_finished_callback()
            mock_consumer.store_offsets.assert_not_called()

    def test_batch_finished_callback_raises_input_warning_on_kafka_exception(self):
        with (
            mock.patch.object(self.object, "_consumer") as mock_consumer,
            mock.patch.object(self.object, "_last_valid_record", new={0: "message"}),
        ):
            return_sequence = [KafkaException("test error"), None]

            def raise_generator(return_sequence):
                return list(reversed(return_sequence)).pop()

            mock_consumer.store_offsets.side_effect = raise_generator(return_sequence)

            with pytest.raises(InputWarning):
                self.object.batch_finished_callback()

    def test_get_next_raises_critical_input_error_if_not_a_dict(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None
            mock_record.value.return_value = b'[{"element":"in list"}]'

            mock_consumer.poll.return_value = mock_record

            with pytest.raises(CriticalInputError, match=r"not a dict"):
                self.object.get_next(1)

    def test_get_next_raises_critical_input_error_if_invalid_json(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None
            mock_record.value.return_value = b"I'm not valid json"

            mock_consumer.poll.return_value = mock_record

            with pytest.raises(CriticalInputError, match=r"not a valid json"):
                self.object.get_next(1)

    def test_get_event_returns_event_and_raw_event(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_record = mock.MagicMock()
            mock_record.error.return_value = None
            mock_record.value.return_value = b'{"element":"in list"}'

            mock_consumer.poll.return_value = mock_record

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

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_event_raises_exception_if_input_invalid_json(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '{"invalid_json"}'.encode("utf8")
        with pytest.raises(
            CriticalInputParsingError,
            match=(
                r"Input record value is not a valid json string ->"
                r" event was written to error output if configured"
            ),
        ) as error:
            self.object._get_event(0.001)
        assert error.value.raw_input == b'{"invalid_json"}'

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_event_raises_exception_if_input_not_utf(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '{"not_utf-8": \xfc}'.encode("cp1252")
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
        return_value = b'{"invalid": "json'
        self.object._get_raw_event = mock.MagicMock(return_value=return_value)
        with pytest.raises(CriticalInputParsingError, match="is not a valid json"):
            self.object.get_next(0.01)

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
        kafka_input = Factory.create({"kafka_input": self.CONFIG})
        injected_config = {
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "client.id": socket.getfqdn(),
            "auto.offset.reset": "earliest",
            "session.timeout.ms": "6000",
            "statistics.interval.ms": "30000",
            "bootstrap.servers": "testserver:9092",
            "group.id": "testgroup",
            "group.instance.id": f"{socket.getfqdn().strip('.')}-PipelineNone-pid{os.getpid()}",
            "logger": logger,
            "on_commit": kafka_input._commit_callback,
            "stats_cb": kafka_input._stats_callback,
            "error_cb": kafka_input._error_callback,
        }

        with mock.patch("logprep.connector.confluent_kafka.input.Consumer") as mock_consumer:
            _ = kafka_input._consumer
            mock_consumer.assert_called_with(injected_config)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_auto_offset_store_and_auto_commit_are_managed_by_connector(self, mock_consumer):
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

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    @mock.patch("logprep.connector.confluent_kafka.input.AdminClient")
    def test_client_id_can_be_overwritten(self, _, mock_consumer):
        input_config = deepcopy(self.CONFIG)
        input_config["kafka_config"]["client.id"] = "thisclientid"
        kafka_input = Factory.create({"test": input_config})
        metadata = mock.MagicMock()
        metadata.topics = [kafka_input._config.topic]
        kafka_input._admin.list_topics.return_value = metadata
        kafka_input.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("client.id") == "thisclientid"
        assert not mock_consumer.call_args[0][0].get("client.id") == socket.getfqdn()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    @mock.patch("logprep.connector.confluent_kafka.input.AdminClient")
    def test_statistics_interval_can_be_overwritten(self, _, mock_consumer):
        input_config = deepcopy(self.CONFIG)
        input_config["kafka_config"]["statistics.interval.ms"] = "999999999"
        kafka_input = Factory.create({"test": input_config})
        metadata = mock.MagicMock()
        metadata.topics = [kafka_input._config.topic]
        kafka_input._admin.list_topics.return_value = metadata
        kafka_input.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("statistics.interval.ms") == "999999999"

    def test_raises_fatal_input_error_if_poll_raises_runtime_error(
        self,
    ):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.poll.side_effect = RuntimeError("test error")

            with pytest.raises(FatalInputError, match="test error"):
                self.object.get_next(0.01)

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

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_lost_callback_counts_warnings_and_logs(self, mock_consumer):
        self.object.metrics.number_of_warnings = 0
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.object._lost_callback(mock_partitions)
        mock_warning.assert_called()
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

    def test_health_returns_true_if_no_error(self):
        with mock.patch.object(self.object, "_admin") as mock_admin:
            metadata = mock.MagicMock()
            metadata.topics = [self.object._config.topic]
            mock_admin.list_topics.return_value = metadata

            assert self.object.health()

    def test_health_returns_false_if_topic_not_present(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            metadata = mock.MagicMock()
            metadata.topics = ["not_the_topic"]
            mock_consumer.list_topics.return_value = metadata

            assert not self.object.health()

    def test_health_returns_false_on_kafka_exception(self):
        with mock.patch.object(self.object, "_consumer") as mock_consumer:
            mock_consumer.list_topics.side_effect = KafkaException("test error")

            assert not self.object.health()

    def test_health_logs_error_on_kafka_exception(self):
        with (
            mock.patch.object(self.object, "_consumer") as mock_consumer,
            mock.patch("logging.Logger.error") as mock_error,
        ):
            mock_consumer.list_topics.side_effect = KafkaException("test error")

            self.object.health()

        mock_error.assert_called()

    def test_health_counts_metrics_on_kafka_exception(self):
        kafka_input = Factory.create({"kafka_input": self.CONFIG})
        kafka_input.metrics.number_of_errors = 0

        with mock.patch.object(kafka_input, "_consumer") as mock_consumer:
            mock_consumer.list_topics.side_effect = KafkaException("test error")

            assert not kafka_input.health()
            assert kafka_input.metrics.number_of_errors == 1

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
    @mock.patch("logprep.connector.confluent_kafka.input.AdminClient")
    def test_set_security_related_config_in_admin_client(
        self, admin_client, kafka_config_update, expected_admin_client_config
    ):
        new_kafka_config = deepcopy(self.CONFIG)
        new_kafka_config["kafka_config"].update(kafka_config_update)
        input_connector = Factory.create({"input_connector": new_kafka_config})
        _ = input_connector._admin
        admin_client.assert_called_with(expected_admin_client_config)
