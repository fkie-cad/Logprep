# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init

import json
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from confluent_kafka import OFFSET_BEGINNING, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient
from confluent_kafka.aio import AIOConsumer

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.input import (
    CriticalInputParsingError,
    FatalInputError,
    InputWarning,
)
from logprep.ng.connector.confluent_kafka.input import ConfluentKafkaInput, logger
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaMetadata
from logprep.ng.event.error_event import ErrorEvent
from logprep.util.helper import get_dotted_field_value
from tests.unit.ng.connector.base import BaseInputTestCase

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class TestConfluentKafkaInput(BaseInputTestCase[ConfluentKafkaInput]):
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

    @pytest.fixture
    def mock_consumer(self):
        # TODO do we need the whole path, or can we make this prettier?
        with mock.patch(
            "logprep.ng.connector.confluent_kafka.input.AIOConsumer", spec=AIOConsumer
        ) as mock_consumer:
            mock_consumer.return_value = mock_consumer
            mock_consumer._consumer = mock.MagicMock()
            mock_consumer._consumer.memberid.return_value = 42
            yield mock_consumer

    @pytest.fixture
    def mock_admin(self):
        with mock.patch(
            "logprep.ng.connector.confluent_kafka.input.AdminClient", spec=AdminClient
        ) as admin:
            admin.return_value = admin
            yield admin

    @pytest.fixture
    def mock_executor(self):
        with mock.patch(
            "logprep.ng.connector.confluent_kafka.input.concurrent.futures.ThreadPoolExecutor",
            spec=ThreadPoolExecutor,
        ) as executor:
            executor.return_value = executor
            yield executor

    @pytest.fixture(autouse=True)
    def autouse_central_fixtures(self, mock_consumer, mock_admin, mock_executor):
        yield mock_consumer, mock_admin, mock_executor  # return technically not required

    async def test_client_id_is_set_to_hostname(self):
        await self.object.setup()
        assert self.object._kafka_config.get("client.id") == socket.getfqdn()

    async def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config})

    async def test_error_callback_logs_error(self):
        self.object.metrics.number_of_errors = 0
        with mock.patch("logging.Logger.error") as mock_error:
            test_error = Exception("test error")
            await self.object._error_callback(test_error)
            mock_error.assert_called()
            mock_error.assert_called_with("%s: %s", self.object.describe(), test_error)
        assert self.object.metrics.number_of_errors == 1

    async def test_stats_callback_sets_metric_objetc_attributes(self):
        librdkafka_metrics = tuple(
            filter(lambda x: x.startswith("librdkafka"), self.expected_metrics)
        )
        for metric in librdkafka_metrics:
            setattr(self.object.metrics, metric, 0)

        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        await self.object._stats_callback(json_string)
        stats_dict = json.loads(json_string)
        for metric in librdkafka_metrics:
            metric_name = metric.replace("librdkafka_", "").replace("cgrp_", "cgrp.")
            metric_value = get_dotted_field_value(stats_dict, metric_name)
            assert getattr(self.object.metrics, metric) == metric_value, metric

    async def test_stats_set_age_metric_explicitly(self):
        self.object.metrics.librdkafka_age = 0
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        await self.object._stats_callback(json_string)
        assert self.object.metrics.librdkafka_age == 1337

    async def test_kafka_config_is_immutable(self):
        await self.object.setup()
        with pytest.raises(TypeError):
            self.object._config.kafka_config["client.id"] = "test"

    async def test_get_next_returns_none_if_no_records(self, mock_consumer):
        await self.object.setup()

        mock_consumer.poll.return_value = None

        event = await self.object.get_next(1)
        assert event is None

        await self.object.shut_down()

    async def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(
        self, mock_consumer
    ):
        mock_kafka_message = mock.MagicMock()
        mock_kafka_message.error.return_value = KafkaError(
            error=3,
            reason="Subscribed topic not available: (Test Instance Name) : "
            "Broker: Unknown topic or partition",
            fatal=False,
            retriable=False,
            txn_requires_abort=False,
        )

        await self.object.setup()

        mock_consumer.poll.return_value = mock_kafka_message

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "A confluent-kafka record contains an error code" in error_event.data["reason"]

        await self.object.shut_down()

    async def test_shut_down_calls_consumer_close(self, mock_consumer):
        await self.object.setup()
        await self.object.shut_down()

        mock_consumer.close.assert_called_once()

    # TODO reintroduce batch_finished_callback?
    # async def test_batch_finished_callback_calls_store_offsets(self, mock_consumer):
    #     input_config = deepcopy(self.CONFIG)
    #     kafka_input = Factory.create({"test": input_config})

    #     kafka_consumer = kafka_input._consumer
    #     message = "test message"
    #     kafka_input._last_valid_record = message
    #     kafka_input.batch_finished_callback()
    #     kafka_consumer.store_offsets.assert_called()
    #     kafka_consumer.store_offsets.assert_called_with(message=message)

    #     kafka_input.shut_down()

    # @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    # async def test_batch_finished_callback_does_not_call_store_offsets(self, _):
    #     input_config = deepcopy(self.CONFIG)
    #     kafka_input = Factory.create({"test": input_config})

    #     kafka_consumer = kafka_input._consumer
    #     kafka_input._last_valid_record = None
    #     kafka_input.batch_finished_callback()
    #     kafka_consumer.store_offsets.assert_not_called()

    #     kafka_input.shut_down()

    # @mock.patch("logprep.ng.connector.confluent_kafka.input.Consumer")
    # async def test_batch_finished_callback_raises_input_warning_on_kafka_exception(self, _):
    #     input_config = deepcopy(self.CONFIG)
    #     kafka_input = Factory.create({"test": input_config})

    #     kafka_consumer = kafka_input._consumer
    #     return_sequence = [KafkaException("test error"), None]

    #     def raise_generator(return_sequence):
    #         return list(reversed(return_sequence)).pop()

    #     kafka_consumer.store_offsets.side_effect = raise_generator(return_sequence)
    #     kafka_input._last_valid_record = {0: "message"}
    #     with pytest.raises(InputWarning):
    #         kafka_input.batch_finished_callback()

    #     kafka_input.shut_down()

    async def test_get_next_raises_critical_input_error_if_not_a_dict(self, mock_consumer):
        await self.object.setup()

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")

        mock_consumer.poll.return_value = mock_record

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "not a dict" in error_event.data["reason"]

        await self.object.shut_down()

    async def test_get_next_raises_critical_input_error_if_invalid_json(self, mock_consumer):
        await self.object.setup()

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.value.return_value = "I'm not valid json".encode("utf8")

        mock_consumer.poll.return_value = mock_record

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "not a valid json string" in error_event.data["reason"]

        await self.object.shut_down()

    async def test_get_event_returns_event_and_raw_event(self, mock_consumer):
        await self.object.setup()

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42

        mock_consumer.poll.return_value = mock_record

        event, raw_event, metadata = await self.object._get_event(0.001)
        assert event == {"element": "in list"}
        assert raw_event == '{"element":"in list"}'.encode("utf8")
        assert metadata == ConfluentKafkaMetadata(partition=1, offset=42)

    async def test_get_raw_event_is_callable(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")

        mock_consumer.poll.return_value = mock_record

        await self.object.setup()

        result = await self.object._get_raw_event(0.001)

        assert result

    async def test_get_event_raises_exception_if_input_invalid_json(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.value.return_value = '{"invalid_json"}'.encode("utf8")

        mock_consumer.poll.return_value = mock_record

        await self.object.setup()

        with pytest.raises(
            CriticalInputParsingError,
            match=(
                r"Input record value is not a valid json string ->"
                r" event was written to error output if configured"
            ),
        ) as error:
            await self.object._get_event(0.001)
        assert error.value.raw_input == b'{"invalid_json"}'

    async def test_get_event_raises_exception_if_input_not_utf(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None

        mock_record.value.return_value = '{"not_utf-8": \xfc}'.encode("cp1252")

        mock_consumer.poll.return_value = mock_record

        await self.object.setup()

        with pytest.raises(
            CriticalInputParsingError,
            match=(
                r"Input record value is not \'utf-8\' encoded ->"
                r" event was written to error output if configured"
            ),
        ) as error:
            await self.object._get_event(0.001)
        assert error.value.raw_input == "b'{\"not_utf-8\": \\xfc}'"

    # async def test_setup_raises_fatal_input_error_on_invalid_config(self):
    #     self.object = self._create_test_instance(
    #         config_patch={
    #             "kafka_config": {
    #                 "bootstrap.servers": "testinstance:9092",
    #                 "group.id": "sapsal",
    #                 "myconfig": "the config",
    #             }
    #         }
    #     )
    #     with pytest.raises(FatalInputError, match="No such configuration property"):
    #         await self.object.setup()

    async def test_get_next_raises_critical_input_parsing_error(self):
        await self.object.setup()

        mock_message = mock.MagicMock()
        mock_message.value.return_value = b'{"invalid": "json'

        self.object._get_raw_event = mock.AsyncMock(return_value=mock_message)

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "Input record value is not a valid json string" in error_event.data["reason"]

    async def test_commit_callback_raises_warning_error_and_counts_failures(self):
        with pytest.raises(InputWarning, match="Could not commit offsets"):
            await self.object._commit_callback(Exception, ["topic_partition"])
            assert self.object._commit_failures == 1

    async def test_commit_callback_counts_commit_success(self):
        self.object.metrics.commit_success = 0
        await self.object._commit_callback(None, [mock.MagicMock()])
        assert self.object.metrics.commit_success == 1

    async def test_commit_callback_sets_committed_offsets(self):
        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        topic_partition = mock.MagicMock()
        topic_partition.partition = 99
        topic_partition.offset = 666
        await self.object._commit_callback(None, [topic_partition])
        call_args = 666, {"description": "topic: test_input_raw - partition: 99"}
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(*call_args)

    async def test_default_config_is_injected(self, mock_consumer, mock_executor):
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
            "on_commit": self.object._commit_callback,
            "stats_cb": self.object._stats_callback,
            "error_cb": self.object._error_callback,
        }

        await self.object.setup()
        mock_consumer.assert_called_with(injected_config, executor=mock_executor)

    async def test_auto_offset_store_and_auto_commit_are_managed_by_connector(self, mock_consumer):
        self.object = self._create_test_instance(
            config_patch={
                "kafka_config": {
                    "enable.auto.offset.store": "true",
                    "enable.auto.commit": "false",
                    "bootstrap.servers": "testserver:9092",
                    "group.id": "testgroup",
                }
            }
        )

        await self.object.setup()

        mock_consumer.assert_called()

        actual_kafka_config = mock_consumer.call_args[0][0]
        assert actual_kafka_config.get("enable.auto.offset.store") == "false"
        assert actual_kafka_config.get("enable.auto.commit") == "true"

        await self.object.shut_down()

    async def test_client_id_can_be_overwritten(self, mock_consumer):
        self.object = self._create_test_instance(
            config_patch={
                "kafka_config": {
                    "bootstrap.servers": "testserver:9092",
                    "group.id": "testgroup",
                    "client.id": "thisclientid",
                }
            }
        )
        await self.object.setup()

        mock_consumer.assert_called()
        actual_kafka_config = mock_consumer.call_args[0][0]
        assert actual_kafka_config.get("client.id") == "thisclientid"
        assert not actual_kafka_config.get("client.id") == socket.getfqdn()

        await self.object.shut_down()

    async def test_statistics_interval_can_be_overwritten(self, mock_consumer):
        self.object = self._create_test_instance(
            config_patch={
                "kafka_config": {
                    "bootstrap.servers": "testserver:9092",
                    "group.id": "testgroup",
                    "statistics.interval.ms": "999999999",
                }
            }
        )
        await self.object.setup()

        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("statistics.interval.ms") == "999999999"

        await self.object.shut_down()

    async def test_raises_fatal_input_error_if_poll_raises_runtime_error(self, mock_consumer):
        mock_consumer.poll.side_effect = RuntimeError("test error")

        await self.object.setup()

        with pytest.raises(FatalInputError, match="test error"):
            await self.object.get_next(0.01)

    async def test_raises_value_error_if_mandatory_parameters_not_set(self):
        expected_error_message = r"keys are missing: {'(bootstrap.servers|group.id)', '(bootstrap.servers|group.id)'}"  # pylint: disable=line-too-long
        with pytest.raises(InvalidConfigurationError, match=expected_error_message):
            self._create_test_instance(
                config_patch={
                    "kafka_config": {
                        # "bootstrap.servers": "testserver:9092",
                        # "group.id": "testgroup",
                    }
                }
            )

    @pytest.mark.parametrize(
        "metric_name",
        [
            "current_offsets",
            "committed_offsets",
        ],
    )
    async def test_offset_metrics_not_initialized_with_default_label_values(self, metric_name):
        metric = getattr(self.object.metrics, metric_name)
        metric_object = metric.tracker.collect()[0]
        assert len(metric_object.samples) == 0

    async def test_lost_callback_counts_warnings_and_logs(self, mock_consumer):
        await self.object.setup()
        self.object.metrics.number_of_warnings = 0
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            await self.object._lost_callback(mock_consumer, mock_partitions)
        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings == 1

    async def test_commit_callback_sets_offset_to_0_for_special_offsets(self):
        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        mock_partitions[0].offset = OFFSET_BEGINNING
        await self.object._commit_callback(None, mock_partitions)
        expected_labels = {
            "description": f"topic: test_input_raw - partition: {mock_partitions[0].partition}"
        }
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(0, expected_labels)

    async def test_assign_callback_sets_offsets_and_logs_info(self):
        await self.object.setup()

        self.object.metrics.committed_offsets.add_with_labels = mock.MagicMock()
        self.object.metrics.current_offsets.add_with_labels = mock.MagicMock()
        mock_partitions = [mock.MagicMock()]
        mock_partitions[0].offset = OFFSET_BEGINNING
        with mock.patch("logging.Logger.info") as mock_info:
            await self.object._assign_callback(None, mock_partitions)
        expected_labels = {
            "description": f"topic: test_input_raw - partition: {mock_partitions[0].partition}"
        }
        mock_info.assert_called()
        self.object.metrics.committed_offsets.add_with_labels.assert_called_with(0, expected_labels)
        self.object.metrics.current_offsets.add_with_labels.assert_called_with(0, expected_labels)

    async def test_revoke_callback_logs_warning_and_counts(self):
        await self.object.setup()

        self.object.metrics.number_of_warnings = 0
        self.object.output_connector = mock.AsyncMock()
        mock_partitions = [mock.MagicMock()]
        with mock.patch("logging.Logger.warning") as mock_warning:
            await self.object._revoke_callback(None, mock_partitions)
        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings == 1

    async def test_revoke_callback_calls_batch_finished_callback(self):
        await self.object.setup()

        self.object.output_connector = mock.AsyncMock()
        self.object.batch_finished_callback = mock.AsyncMock()
        mock_partitions = [mock.MagicMock()]
        await self.object._revoke_callback(None, mock_partitions)
        self.object.batch_finished_callback.assert_called()

    async def test_revoke_callback_logs_error_if_consumer_closed(self, mock_consumer, caplog):
        mock_consumer._consumer.memberid.side_effect = RuntimeError("Consumer is closed")

        await self.object.setup()
        await self.object._revoke_callback(None, topic_partitions=[mock.MagicMock()])
        assert re.search(r"ERROR.*Consumer is closed", caplog.text)

    async def test_health_returns_true_if_no_error(self, mock_admin):
        mock_admin.list_topics.return_value.topics = ["test-topic"]
        self.object = self._create_test_instance(config_patch={"topic": "test-topic"})

        await self.object.setup()
        assert await self.object.health()
        await self.object.shut_down()

    async def test_health_returns_false_if_topic_not_present(self, mock_admin):
        mock_admin.list_topics.return_value.topics = ["not_the_topic"]
        await self.object.setup()
        assert not await self.object.health()

    async def test_health_returns_false_on_kafka_exception(self, mock_consumer):
        mock_consumer.list_topics.side_effect = KafkaException("test error")
        await self.object.setup()
        assert not await self.object.health()

    async def test_health_logs_error_on_kafka_exception(self, mock_consumer):
        mock_consumer.list_topics.side_effect = KafkaException("test error")

        await self.object.setup()
        with mock.patch("logging.Logger.error") as mock_error:
            await self.object.health()

            mock_error.assert_called()

    async def test_health_counts_metrics_on_kafka_exception(self, mock_admin):
        mock_admin.list_topics.side_effect = KafkaException("test error")

        await self.object.setup()
        self.object.metrics.number_of_errors = 0
        assert not await self.object.health()
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
    async def test_set_security_related_config_in_admin_client(
        self, mock_admin, kafka_config_update, expected_admin_client_config
    ):
        self.object = self._create_test_instance(
            config_patch={"kafka_config": self.CONFIG["kafka_config"] | kafka_config_update}
        )
        await self.object.setup()
        mock_admin.assert_called_with(expected_admin_client_config)
