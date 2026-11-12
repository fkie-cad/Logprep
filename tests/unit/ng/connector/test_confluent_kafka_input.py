# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init

import asyncio
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from confluent_kafka import (
    OFFSET_BEGINNING,
    OFFSET_INVALID,
    KafkaError,
    KafkaException,
    TopicPartition,
)
from confluent_kafka.aio import AIOConsumer

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.event import ErrorEvent, LogEvent
from logprep.ng.abc.input import (
    CriticalInputError,
    FatalInputError,
    InputWarning,
)
from logprep.ng.connector.confluent_kafka.input import (
    _DEFAULT_MEMBER_ID,
    ConfluentKafkaInput,
)
from logprep.ng.connector.confluent_kafka.input import logger as kafka_input_logger
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaInputMeta
from logprep.util.helper import FieldValue, get_dotted_field_value
from tests.unit.ng.connector.base import BaseInputTestCase

MODULE = "logprep.ng.connector.confluent_kafka.input"
KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


@pytest.fixture(name="real_consumer")
def fixture_real_consumer():
    yield


@pytest.fixture(name="mock_consumer")
def fixture_mock_consumer(request):
    if fixture_real_consumer.name in request.fixturenames:
        yield
        return
    with mock.patch(f"{MODULE}.AIOConsumer", spec=AIOConsumer) as mock_consumer:
        mock_consumer.return_value = mock_consumer
        mock_consumer._consumer = mock.MagicMock()
        mock_consumer._consumer.memberid.return_value = 42
        yield mock_consumer


@pytest.fixture(name="mock_executor")
def fixture_mock_executor():
    with mock.patch(
        f"{MODULE}.concurrent.futures.ThreadPoolExecutor",
        spec=ThreadPoolExecutor,
    ) as executor:
        executor.return_value = executor
        yield executor


@pytest.fixture(autouse=True)
def autouse_central_fixtures(mock_consumer, mock_executor):
    yield mock_consumer, mock_executor


def register_partitions(connector, *partitions, offset=0):
    """Simulate an assignment, which the connector needs before it accepts messages."""
    for partition in partitions:
        connector._register_partition(partition, offset)


class TestConfluentKafkaInput(BaseInputTestCase[ConfluentKafkaInput]):
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
        "logprep_confluent_kafka_input_revoke_drain_timeouts",
        "logprep_confluent_kafka_input_revoke_drain_seconds",
        "logprep_confluent_kafka_input_orphaned_acknowledgements",
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

    def _create_log_event(
        self,
        data: dict[str, FieldValue],
        original: bytes | None = None,
        partition: int = 0,
        offset: int = 0,
    ):
        return LogEvent(
            data,
            original=original,
            input_meta=ConfluentKafkaInputMeta(partition=partition, offset=offset),
        )

    async def test_client_id_is_set_to_hostname(self):
        await self.object.setup()
        assert self.object._kafka_config.get("client.id") == socket.getfqdn()

    async def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config})

    async def test_error_callback_logs_error(self):
        with mock.patch("logging.Logger.error") as mock_error:
            test_error = Exception("test error")
            await self.object._error_callback(test_error)
            mock_error.assert_called()
            mock_error.assert_called_with("%s: %s", self.object.description, test_error)
        assert self.object.metrics.number_of_errors.value == 1

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
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        await self.object._stats_callback(json_string)
        assert self.object.metrics.librdkafka_age.value == 1337

    async def test_get_next_returns_none_if_no_records(self, mock_consumer):
        await self.object.setup()

        mock_consumer.consume.return_value = []

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

        mock_consumer.consume.return_value = [mock_kafka_message]

        with pytest.raises(CriticalInputError):
            await self.object.get_next(1)

        await self.object.shut_down()

    async def test_shut_down_calls_consumer_close(self, mock_consumer):
        await self.object.setup()
        await self.object.shut_down()

        mock_consumer.close.assert_called_once()

    async def _stored_offsets(self, mock_consumer) -> list[tuple[int, int]]:
        """Store what is pending, as the consumer's owner would, and return the offsets."""
        await self.object._store_pending_offsets()
        # TopicPartition equality ignores the offset, so compare the values
        return sorted(
            (tp.partition, tp.offset)
            for tp in mock_consumer.store_offsets.call_args.kwargs["offsets"]
        )

    async def test_acknowledge_stores_the_next_gap_free_offset(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0)

        event = self._create_log_event({"some": "event"})
        await self.object.acknowledge([event])

        assert await self._stored_offsets(mock_consumer) == [(0, 1)]

    async def test_acknowledge_holds_offsets_back_until_the_gap_is_closed(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0)

        # offset 1 is missing, so nothing above it may be stored yet
        await self.object.acknowledge(
            [self._create_log_event({"n": n}, offset=n) for n in (0, 2, 3)]
        )
        assert await self._stored_offsets(mock_consumer) == [(0, 1)]

        await self.object.acknowledge([self._create_log_event({"n": 1}, offset=1)])
        assert await self._stored_offsets(mock_consumer) == [(0, 4)]

    async def test_acknowledge_does_not_call_store_offsets_if_no_offset_committable(
        self, mock_consumer
    ):
        await self.object.setup()
        register_partitions(self.object, 0, offset=10)

        # already committed, so it does not advance the watermark
        await self.object.acknowledge([self._create_log_event({"some": "event"}, offset=1)])
        await self.object._store_pending_offsets()

        mock_consumer.store_offsets.assert_not_called()

    async def test_acknowledge_ignores_offsets_of_unregistered_partitions(self, mock_consumer):
        await self.object.setup()

        await self.object.acknowledge([self._create_log_event({"some": "event"})])
        await self.object._store_pending_offsets()

        mock_consumer.store_offsets.assert_not_called()

    async def test_acknowledge_does_not_touch_the_consumer(self, mock_consumer):
        # offsets to be committed are only stored in memory and consume path will handle them later
        await self.object.setup()
        register_partitions(self.object, 0)
        mock_consumer.reset_mock()

        await self.object.acknowledge([self._create_log_event({"some": "event"})])

        assert mock_consumer.mock_calls == []

    async def test_pending_offsets_are_stored_before_consume(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0)
        await self.object.acknowledge([self._create_log_event({"some": "event"})])
        mock_consumer.reset_mock()
        mock_consumer.consume.return_value = []

        await self.object._get_raw_event(0.001)

        assert [call[0] for call in mock_consumer.mock_calls] == ["store_offsets", "consume"]

    async def test_store_warns_and_retries_on_kafka_exception(self, mock_consumer, caplog):
        await self.object.setup()
        register_partitions(self.object, 0)
        await self.object.acknowledge([self._create_log_event({"some": "event"})])
        mock_consumer.store_offsets.side_effect = KafkaException("test error")

        await self.object._store_pending_offsets()

        assert re.search(r"WARNING.*could not store offsets.*test error", caplog.text)
        assert self.object.metrics.number_of_warnings.value == 1

        mock_consumer.store_offsets.side_effect = None
        assert await self._stored_offsets(mock_consumer) == [(0, 1)]
        mock_consumer.store_offsets.reset_mock()
        await self.object._store_pending_offsets()
        mock_consumer.store_offsets.assert_not_called()

    async def test_acknowledge_handles_out_of_order_offsets(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0, offset=100)

        await self.object.acknowledge(
            [self._create_log_event({"n": n}, offset=n) for n in (102, 100, 101)]
        )

        assert await self._stored_offsets(mock_consumer) == [(0, 103)]
        assert self.object._partitions[0].committable_offsets == set()

    async def test_acknowledge_advances_several_partitions_in_one_call(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0, offset=100)
        register_partitions(self.object, 1, offset=200)

        await self.object.acknowledge(
            [
                self._create_log_event({"n": 0}, partition=0, offset=100),
                self._create_log_event({"n": 1}, partition=0, offset=101),
                self._create_log_event({"n": 2}, partition=1, offset=200),
            ]
        )

        assert await self._stored_offsets(mock_consumer) == [(0, 102), (1, 201)]

    async def test_acknowledge_keeps_offsets_above_a_gap_committable(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0, offset=100)

        await self.object.acknowledge(
            [self._create_log_event({"n": n}, offset=n) for n in (100, 101, 104, 102, 106)]
        )

        assert await self._stored_offsets(mock_consumer) == [(0, 103)]
        assert self.object._partitions[0].committable_offsets == {104, 106}

    async def test_acknowledge_is_idempotent(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0, offset=100)
        events = [self._create_log_event({"n": n}, offset=n) for n in (100, 101)]

        await self.object.acknowledge(events)
        assert await self._stored_offsets(mock_consumer) == [(0, 102)]

        mock_consumer.store_offsets.reset_mock()
        await self.object.acknowledge(events)
        await self.object._store_pending_offsets()
        mock_consumer.store_offsets.assert_not_called()

    async def test_acknowledge_warns_and_skips_already_committed_offsets(
        self, mock_consumer, caplog
    ):
        await self.object.setup()
        register_partitions(self.object, 0, offset=100)

        await self.object.acknowledge(
            [
                self._create_log_event({"n": 0}, offset=99),
                self._create_log_event({"n": 1}, offset=100),
            ]
        )

        assert "offset 99 already committed" in caplog.text
        assert await self._stored_offsets(mock_consumer) == [(0, 101)]

    async def test_acknowledge_warns_on_offsets_of_unregistered_partitions(self, caplog):
        await self.object.setup()

        await self.object.acknowledge(
            [self._create_log_event({"n": n}, partition=9, offset=n) for n in range(3)]
        )

        assert caplog.text.count("discarded 3 acknowledgements for released partitions") == 1
        assert self.object.metrics.orphaned_acknowledgements.value == 3

    async def test_acknowledge_handles_a_full_batch_of_offsets(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 0)

        await self.object.acknowledge(
            [self._create_log_event({"n": n}, offset=n) for n in range(10_000)]
        )

        assert await self._stored_offsets(mock_consumer) == [(0, 10_000)]
        assert self.object._partitions[0].committable_offsets == set()

    async def test_revoke_warns_about_offsets_that_were_ready_to_commit(self, caplog):
        await self.object.setup()
        register_partitions(self.object, 3, offset=100)
        # 100 is missing, so 101 can never be stored and is lost on revocation
        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=3, offset=101)])

        await self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])

        assert "offsets [101] of partition 3 were ready to commit and are now lost" in caplog.text

    async def test_revoke_does_not_warn_if_nothing_was_pending(self, caplog):
        await self.object.setup()
        register_partitions(self.object, 3, offset=100)
        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=3, offset=100)])

        await self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])

        assert "ready to commit and are now lost" not in caplog.text

    async def test_get_next_raises_critical_input_error_if_not_a_dict(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 1)

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")

        mock_consumer.consume.return_value = [mock_record]

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "not a valid json string representing an object" in error_event.reason

        await self.object.shut_down()

    async def test_get_next_raises_critical_input_error_if_invalid_json(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 1)

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42
        mock_record.value.return_value = "I'm not valid json".encode("utf8")

        mock_consumer.consume.return_value = [mock_record]

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "not a valid json string" in error_event.reason

        await self.object.shut_down()

    async def test_get_event_returns_event(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 1)

        mock_record = mock.MagicMock()

        mock_record.error.return_value = None
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42

        mock_consumer.consume.return_value = [mock_record]

        event = await self.object._get_event(0.001)
        assert event.data == {"element": "in list"}
        assert event.original == '{"element":"in list"}'.encode("utf8")
        assert event.input_meta == ConfluentKafkaInputMeta(partition=1, offset=42)

    async def test_get_raw_event_is_callable(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.value.return_value = '{"element":"in list"}'.encode("utf8")
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42

        mock_consumer.consume.return_value = [mock_record]

        await self.object.setup()
        register_partitions(self.object, 1)

        result = await self.object._get_raw_event(0.001)

        assert result

    async def test_get_event_raises_exception_if_input_invalid_json(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.value.return_value = '{"invalid_json"}'.encode("utf8")
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42

        mock_consumer.consume.return_value = [mock_record]

        await self.object.setup()
        register_partitions(self.object, 1)

        error_event = await self.object._get_event(0.001)
        assert isinstance(error_event, ErrorEvent)
        assert "is not a valid json string" in error_event.reason

    async def test_get_event_returns_error_if_not_utf8(self, mock_consumer):
        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.value.return_value = '{"not_utf-8": \xfc}'.encode("cp1252")
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 42

        mock_consumer.consume.return_value = [mock_record]

        await self.object.setup()
        register_partitions(self.object, 1)

        error_event = await self.object._get_event(0.001)
        assert isinstance(error_event, ErrorEvent)
        assert "is not a valid json string" in error_event.reason

    @pytest.mark.usefixtures("real_consumer")
    async def test_setup_raises_fatal_input_error_on_invalid_config(self):
        self.object = self._create_test_instance(
            config_patch={
                "kafka_config": {
                    "bootstrap.servers": "testinstance:9092",
                    "group.id": "sapsal",
                    "myconfig": "the config",
                }
            }
        )
        with pytest.raises(FatalInputError):
            # use real consumer __init__ for validation, but never actually subscribe
            with mock.patch(f"{MODULE}.AIOConsumer.subscribe") as mock_subscribe:
                await self.object.setup()
        mock_subscribe.assert_not_called()

    async def test_get_next_raises_critical_input_parsing_error(self):
        await self.object.setup()

        self.object._get_raw_event = mock.AsyncMock(
            return_value=(b'{"invalid": "json', ConfluentKafkaInputMeta(partition=0, offset=42))
        )

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert "Input record value is not a valid json string" in error_event.data["errors"]

    async def test_commit_callback_raises_warning_error_and_counts_failures(self):
        with pytest.raises(InputWarning, match="Could not commit offsets"):
            await self.object._commit_callback(Exception, [mock.MagicMock()])
        assert self.object.metrics.commit_failures.value == 1

    async def test_commit_callback_counts_commit_success(self):
        await self.object._commit_callback(None, [])
        assert self.object.metrics.commit_success.value == 1

    def _committed_offset_sample(self, partition: int) -> float:
        description = f"topic: test_input_raw - partition: {partition}"
        return next(
            sample.value
            for sample in self.object.metrics.committed_offsets.collect_samples()
            if sample.labels["description"] == description
        )

    async def test_commit_callback_sets_committed_offsets(self):
        await self.object.setup()
        register_partitions(self.object, 99)

        await self.object._commit_callback(
            None, [TopicPartition("test_input_raw", partition=99, offset=666)]
        )

        assert self._committed_offset_sample(99) == 666

    async def test_commit_callback_sets_offset_to_0_for_special_offsets(self):
        await self.object.setup()
        register_partitions(self.object, 7, offset=5)

        await self.object._commit_callback(
            None, [TopicPartition("test_input_raw", partition=7, offset=OFFSET_BEGINNING)]
        )

        assert self._committed_offset_sample(7) == 0

    async def test_commit_callback_ignores_unregistered_partitions(self):
        await self.object.setup()

        await self.object._commit_callback(
            None, [TopicPartition("test_input_raw", partition=99, offset=666)]
        )

        assert not self.object.metrics.committed_offsets.collect_samples()

    async def test_default_config_is_injected(self, mock_consumer, mock_executor):
        injected_config = {
            "auto.offset.reset": "earliest",
            "statistics.interval.ms": "30000",
            "max.poll.interval.ms": "300000",
            "client.id": socket.getfqdn(),
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "enable.partition.eof": "false",
            "group.protocol": "consumer",
            "bootstrap.servers": "testserver:9092",
            "group.id": "testgroup",
            "logger": kafka_input_logger,
            "stats_cb": self.object._stats_callback,
            "error_cb": self.object._error_callback,
            "on_commit": self.object._commit_callback,
        }

        await self.object.setup()
        mock_consumer.assert_called_with(injected_config, executor=mock_executor)

    @pytest.mark.parametrize(
        "key, guidance",
        [
            ("enable.auto.offset.store", 'enforced as "false"'),
            ("enable.auto.commit", 'enforced as "true"'),
            ("enable.partition.eof", 'enforced as "false"'),
            ("group.protocol", 'enforced as "consumer"'),
            ("session.timeout.ms", "group.consumer.session.timeout.ms on the broker"),
            ("heartbeat.interval.ms", "group.consumer.heartbeat.interval.ms on the broker"),
            ("partition.assignment.strategy", "use group.remote.assignor"),
            ("group.protocol.type", "not applicable"),
        ],
    )
    def test_rejected_kafka_config_names_the_alternative(self, key, guidance):
        kafka_config = {"bootstrap.servers": "testserver:9092", "group.id": "testgroup"}
        with pytest.raises(ValueError, match=re.escape(f"{key}: ") + ".*" + re.escape(guidance)):
            self._create_test_instance(config_patch={"kafka_config": kafka_config | {key: "x"}})

    def test_rejected_kafka_config_lists_keys_sorted(self):
        kafka_config = {
            "bootstrap.servers": "testserver:9092",
            "group.id": "testgroup",
            "session.timeout.ms": "x",
            "group.protocol": "x",
            "enable.auto.commit": "x",
        }
        with pytest.raises(ValueError) as error:
            self._create_test_instance(config_patch={"kafka_config": kafka_config})
        listed = re.findall(r"([\w.]+): ", str(error.value).split("entries: ", 1)[1])
        assert listed == ["enable.auto.commit", "group.protocol", "session.timeout.ms"]

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

    async def test_client_id_defaults_to_the_pod_name_if_set(self, mock_consumer, monkeypatch):
        monkeypatch.setattr(
            "logprep.ng.connector.confluent_kafka.input.ENV_VARS", {"POD_NAME": "logprep-0"}
        )
        await self.object.setup()

        assert mock_consumer.call_args[0][0]["client.id"] == "logprep-0"

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
        mock_consumer.consume.side_effect = RuntimeError("test error")

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
        assert len(metric.collect_samples()) == 0

    async def test_lost_callback_counts_warnings_and_unregisters(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 3)

        with mock.patch("logging.Logger.warning") as mock_warning:
            await self.object._lost_callback(
                mock_consumer, [TopicPartition("test_input_raw", partition=3)]
            )

        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings.value == 1
        assert 3 not in self.object._partitions

    async def test_lost_callback_does_not_wait_for_in_flight_events(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 3)
        self.object._partitions[3].last_dispatched_offset = 99  # never acknowledged

        await asyncio.wait_for(
            self.object._lost_callback(
                mock_consumer, [TopicPartition("test_input_raw", partition=3)]
            ),
            timeout=1,
        )

        assert 3 not in self.object._partitions

    async def test_assign_callback_registers_partition_and_logs_info(self, mock_consumer):
        await self.object.setup()

        mock_consumer.committed.return_value = [
            TopicPartition("test_input_raw", partition=3, offset=42)
        ]

        with mock.patch("logging.Logger.info") as mock_info:
            await self.object._assign_callback(
                None, [TopicPartition("test_input_raw", partition=3, offset=OFFSET_INVALID)]
            )

        mock_info.assert_called()
        assert self.object._partitions[3].next_expected_offset == 42
        assert self._committed_offset_sample(3) == 42

    async def test_revoke_callback_logs_warning_and_unregisters(self):
        await self.object.setup()
        register_partitions(self.object, 3)

        with mock.patch("logging.Logger.warning") as mock_warning:
            await self.object._revoke_callback(
                None, [TopicPartition("test_input_raw", partition=3)]
            )

        mock_warning.assert_called()
        assert self.object.metrics.number_of_warnings.value == 1
        assert 3 not in self.object._partitions

    async def test_assign_callback_logs_error_and_falls_back_if_consumer_closed(
        self, mock_consumer, caplog
    ):
        mock_consumer._consumer.memberid.side_effect = RuntimeError("Consumer is closed")
        mock_consumer.committed.return_value = [
            TopicPartition("test_input_raw", partition=3, offset=42)
        ]

        await self.object.setup()
        await self.object._assign_callback(
            None, [TopicPartition("test_input_raw", partition=3, offset=OFFSET_INVALID)]
        )

        assert re.search(r"ERROR.*Consumer is closed", caplog.text)
        assert self.object._member_id == _DEFAULT_MEMBER_ID

    async def test_revoke_callback_waits_until_in_flight_events_are_acknowledged(
        self, mock_consumer
    ):
        await self.object.setup()
        register_partitions(self.object, 3)
        self.object._partitions[3].last_dispatched_offset = 1

        revoke = asyncio.create_task(
            self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])
        )
        await asyncio.sleep(0)
        assert not revoke.done(), "the partition must be held until its offsets are stored"

        await self.object.acknowledge(
            [self._create_log_event({"n": n}, partition=3, offset=n) for n in (0, 1)]
        )
        mock_consumer.store_offsets.assert_not_called()
        await asyncio.wait_for(revoke, timeout=1)

        assert 3 not in self.object._partitions
        # stored by the callback itself, before it released the partition
        assert await self._stored_offsets(mock_consumer) == [(3, 2)]

    async def test_revoke_callback_returns_immediately_if_nothing_is_in_flight(self):
        await self.object.setup()
        register_partitions(self.object, 3)

        await asyncio.wait_for(
            self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)]),
            timeout=1,
        )

        assert 3 not in self.object._partitions

    @pytest.mark.parametrize(
        "kafka_config, revoke_drain_timeout, expected",
        [
            ({}, None, 290.0),
            ({"max.poll.interval.ms": "60000"}, None, 50.0),
            ({}, 30, 30.0),
        ],
    )
    def test_revoke_drain_timeout_defaults_to_the_maximum(
        self, kafka_config, revoke_drain_timeout, expected
    ):
        config = {"kafka_config": self.CONFIG["kafka_config"] | kafka_config}
        if revoke_drain_timeout is not None:
            config["revoke_drain_timeout"] = revoke_drain_timeout

        connector = self._create_test_instance(config_patch=config)

        assert connector.config.revoke_drain_timeout == expected

    @pytest.mark.parametrize(
        "kafka_config, revoke_drain_timeout, error",
        [
            ({}, 291, "must not exceed 290.0s"),
            ({}, 0, "must be > 0"),
            ({"max.poll.interval.ms": "10000"}, None, "must be > 0"),
        ],
    )
    def test_revoke_drain_timeout_is_validated(self, kafka_config, revoke_drain_timeout, error):
        config = {"kafka_config": self.CONFIG["kafka_config"] | kafka_config}
        if revoke_drain_timeout is not None:
            config["revoke_drain_timeout"] = revoke_drain_timeout

        with pytest.raises(ValueError, match=error):
            self._create_test_instance(config_patch=config)

    async def test_revoke_callback_releases_partitions_and_counts_on_drain_timeout(self, caplog):
        self.object = self._create_test_instance(config_patch={"revoke_drain_timeout": 0.01})
        await self.object.setup()
        register_partitions(self.object, 3)
        self.object._partitions[3].last_dispatched_offset = 99  # never acknowledged

        await self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])

        assert self.object.metrics.revoke_drain_timeouts.value == 1
        assert re.search(r"ERROR.*drain timeout", caplog.text)
        assert 3 not in self.object._partitions

    async def test_revoke_callback_stores_what_was_acknowledged_despite_drain_timeout(
        self, mock_consumer
    ):
        self.object = self._create_test_instance(config_patch={"revoke_drain_timeout": 0.01})
        await self.object.setup()
        register_partitions(self.object, 3)
        self.object._partitions[3].last_dispatched_offset = 99  # 1 to 99 never acknowledged
        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=3, offset=0)])

        await self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])

        assert await self._stored_offsets(mock_consumer) == [(3, 1)]

    async def test_lost_callback_does_not_store_offsets(self, mock_consumer):
        # the assignment is gone, a store would be refused anyway
        await self.object.setup()
        register_partitions(self.object, 3)
        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=3, offset=0)])

        await self.object._lost_callback(None, [TopicPartition("test_input_raw", partition=3)])

        mock_consumer.store_offsets.assert_not_called()

    async def test_revoke_callback_releases_partitions_when_cancelled(self):
        await self.object.setup()
        register_partitions(self.object, 3)
        self.object._partitions[3].last_dispatched_offset = 99

        revoke = asyncio.create_task(
            self.object._revoke_callback(None, [TopicPartition("test_input_raw", partition=3)])
        )
        await asyncio.sleep(0)
        revoke.cancel()
        with pytest.raises(asyncio.CancelledError):
            await revoke

        assert 3 not in self.object._partitions

    async def test_revoke_callback_waits_for_every_revoked_partition(self):
        await self.object.setup()
        register_partitions(self.object, 3, 4)
        for partition in (3, 4):
            self.object._partitions[partition].last_dispatched_offset = 0

        revoke = asyncio.create_task(
            self.object._revoke_callback(
                None,
                [
                    TopicPartition("test_input_raw", partition=3),
                    TopicPartition("test_input_raw", partition=4),
                ],
            )
        )
        await asyncio.sleep(0)

        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=3, offset=0)])
        await asyncio.sleep(0)
        assert not revoke.done(), "partition 4 is still in flight"

        await self.object.acknowledge([self._create_log_event({"n": 0}, partition=4, offset=0)])
        await asyncio.wait_for(revoke, timeout=1)

        assert revoke.done()

    async def test_get_raw_event_drops_messages_of_untracked_partitions(
        self, mock_consumer, caplog
    ):
        await self.object.setup()

        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.partition.return_value = 5  # never assigned
        mock_record.offset.return_value = 42
        mock_record.value.return_value = b'{"some": "event"}'
        mock_consumer.consume.return_value = [mock_record]

        assert await self.object._get_raw_event(0.001) is None
        assert self.object.metrics.number_of_warnings.value == 1
        assert "skipped message of untracked partition 5 at offset 42" in caplog.text

    async def test_get_raw_event_acknowledges_empty_messages(self, mock_consumer, caplog):
        # a null value never reaches the pipeline, so nothing would acknowledge it
        await self.object.setup()
        register_partitions(self.object, 1)

        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 0
        mock_record.value.return_value = None
        mock_consumer.consume.return_value = [mock_record]

        assert await self.object._get_raw_event(0.001) is None
        assert self.object._partitions[1].next_expected_offset == 1
        assert self.object._partitions[1].is_drained
        assert self.object.metrics.number_of_warnings.value == 1
        assert "skipped message without value of partition 1 at offset 0" in caplog.text

    async def test_get_raw_event_tracks_the_last_dispatched_offset(self, mock_consumer):
        await self.object.setup()
        register_partitions(self.object, 1)

        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.partition.return_value = 1
        mock_record.offset.return_value = 7
        mock_record.value.return_value = b'{"some": "event"}'
        mock_consumer.consume.return_value = [mock_record]

        await self.object._get_raw_event(0.001)

        assert self.object._partitions[1].last_dispatched_offset == 7
        assert not self.object._partitions[1].is_drained

    async def test_get_raw_event_skips_messages_without_partition_or_offset(
        self, mock_consumer, caplog
    ):
        await self.object.setup()

        mock_record = mock.MagicMock()
        mock_record.error.return_value = None
        mock_record.partition.return_value = None
        mock_record.offset.return_value = None
        mock_record.value.return_value = b'{"some": "event"}'
        mock_consumer.consume.return_value = [mock_record]

        assert await self.object._get_raw_event(0.001) is None
        assert self.object.metrics.number_of_warnings.value == 1
        assert "skipped message without partition or offset" in caplog.text

    async def test_assign_callback_raises_fatal_error_if_committed_offsets_fail(
        self, mock_consumer
    ):
        await self.object.setup()
        mock_consumer.committed.side_effect = KafkaException("no coordinator")

        with pytest.raises(FatalInputError, match="failed to get committed offsets"):
            await self.object._assign_callback(
                None, [TopicPartition("test_input_raw", partition=3)]
            )

    async def test_assign_callback_raises_fatal_error_if_a_partition_has_no_offset(
        self, mock_consumer
    ):
        await self.object.setup()
        mock_consumer.committed.return_value = [
            TopicPartition("test_input_raw", partition=99, offset=1)
        ]

        with pytest.raises(FatalInputError, match="failed to get committed offset for partition 3"):
            await self.object._assign_callback(
                None, [TopicPartition("test_input_raw", partition=3)]
            )

    @pytest.mark.parametrize("committed_offset", [OFFSET_INVALID, OFFSET_BEGINNING])
    async def test_assign_callback_starts_at_zero_for_special_offsets(
        self, mock_consumer, committed_offset
    ):
        await self.object.setup()
        mock_consumer.committed.return_value = [
            TopicPartition("test_input_raw", partition=3, offset=committed_offset)
        ]

        await self.object._assign_callback(None, [TopicPartition("test_input_raw", partition=3)])

        assert self.object._partitions[3].next_expected_offset == 0

    async def test_health_returns_false_if_base_health_fails(self, mock_consumer):
        # the topic check would pass, so the base health is the only reason to fail
        mock_consumer.list_topics.return_value.topics = ["test_input_raw"]
        await self.object.setup()
        assert await self.object.health()

        with mock.patch(
            "logprep.ng.abc.input.Input.health", new=mock.AsyncMock(return_value=False)
        ):
            assert not await self.object.health()

    async def test_shut_down_is_idempotent(self, mock_consumer):
        await self.object.setup()
        await self.object.shut_down()
        mock_consumer.close.assert_called_once()

        # a second shutdown must not touch the already released resources
        self.object._executor = None
        await self.object.shut_down()
        mock_consumer.close.assert_called_once()

    @staticmethod
    def _before_consuming(connector) -> None:
        """Rewind to the startup phase, where health still asks the broker."""
        connector._consuming = False

    async def test_health_checks_the_topic_before_consuming(self, mock_consumer):
        mock_consumer.list_topics.return_value.topics = ["test-topic"]
        self.object = self._create_test_instance(config_patch={"topic": "test-topic"})
        await self.object.setup()
        self._before_consuming(self.object)

        assert await self.object.health()
        mock_consumer.list_topics.assert_called()
        await self.object.shut_down()

    async def test_health_returns_false_if_topic_not_present(self, mock_consumer):
        mock_consumer.list_topics.return_value.topics = ["not_the_topic"]
        await self.object.setup()
        self._before_consuming(self.object)
        assert not await self.object.health()

    async def test_health_returns_false_on_kafka_exception(self, mock_consumer):
        mock_consumer.list_topics.side_effect = KafkaException("test error")
        await self.object.setup()
        self._before_consuming(self.object)
        assert not await self.object.health()

    async def test_health_logs_error_on_kafka_exception(self, mock_consumer):
        mock_consumer.list_topics.side_effect = KafkaException("test error")
        await self.object.setup()
        self._before_consuming(self.object)
        with mock.patch("logging.Logger.error") as mock_error:
            await self.object.health()

            mock_error.assert_called()

    async def test_health_counts_metrics_on_kafka_exception(self, mock_consumer):
        mock_consumer.list_topics.side_effect = KafkaException("test error")
        await self.object.setup()
        self._before_consuming(self.object)
        assert not await self.object.health()
        assert self.object.metrics.number_of_errors.value == 1

    async def test_health_does_not_call_the_consumer_once_consuming(self, mock_consumer):
        # a call from the health endpoint would wait for any in-flight consume() and
        # could block the executor thread a rebalance callback needs
        await self.object.setup()
        mock_consumer.reset_mock()

        assert await self.object.health()
        assert mock_consumer.mock_calls == []

    async def test_setup_checks_the_topic_before_joining_the_group(self, mock_consumer):
        mock_consumer.list_topics.return_value.topics = ["test-topic"]
        self.object = self._create_test_instance(config_patch={"topic": "test-topic"})
        del self.object._wait_for_health

        await self.object.setup()

        calls = [name for name, *_ in mock_consumer.mock_calls]
        assert calls.index("list_topics") < calls.index("subscribe")

    async def test_setup_does_not_join_the_group_without_the_topic(self, mock_consumer):
        mock_consumer.list_topics.return_value.topics = ["not_the_topic"]
        del self.object._wait_for_health

        with mock.patch("asyncio.sleep"), pytest.raises(SystemExit):
            await self.object.setup()

        mock_consumer.subscribe.assert_not_called()
