# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
import socket
from unittest import mock

import pytest

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    WarningInputError,
)
from tests.unit.connector.base import BaseInputTestCase
from tests.unit.connector.test_confluent_kafka_common import (
    CommonConfluentKafkaTestCase,
)


class TestConfluentKafkaInput(BaseInputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "confluentkafka_input",
        "kafka_config": {"bootstrap.servers": "testserver:9092", "group.id": "testgroup"},
        "topic": "test_input_raw",
    }

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

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_batch_finished_callback_calls_consumer_store_offsets(self, _):
        kafka_consumer = self.object._consumer
        self.object._config.enable_auto_offset_store = False
        self.object._last_valid_records = {"record1": ["dummy"]}
        self.object.batch_finished_callback()
        kafka_consumer.store_offsets.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_raises_critical_input_error_if_not_a_dict(self, _):
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        self.object._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")
        with pytest.raises(CriticalInputError, match=r"could not be parsed as dict"):
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

    def test_on_commit_callback_raises_warning_error(self):
        with pytest.raises(WarningInputError, match="Could not commit offsets"):
            self.object._commit_callback(BaseException, ["topic_partition"])

    def test_error_callback_logs_warnings(self):
        with mock.patch("logging.Logger.warning") as mock_warning:
            test_error = BaseException("test error")
            self.object._error_callback(test_error)
            mock_warning.assert_called()
            mock_warning.assert_called_with(f"{self.object.describe()}: {test_error}")

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_default_config_is_injected(self, mock_consumer):
        injected_config = {
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "client.id": socket.getfqdn(),
            "auto.offset.reset": "earliest",
            "session.timeout.ms": "6000",
            "bootstrap.servers": self.object._config.kafka_config.get("bootstrap.servers"),
            "group.id": "testgroup",
            "logger": self.object._logger,
            "on_commit": self.object._commit_callback,
            "stats_cb": self.object._stats_callback,
            "error_cb": self.object._error_callback,
            "statistics.interval.ms": "1000",
        }
        _ = self.object._consumer
        mock_consumer.assert_called_with(injected_config)

    def test_stats_callback_sets_stats_in_metric_object(self):
        self.object._stats_callback('{"test": "stats"}')
        assert self.object.metrics._stats == {"test": "stats"}

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_client_id_can_be_overwritten(self, mock_consumer):
        self.object.shut_down()
        self.object._config.kafka_config["client.id"] = "thisclientid"
        self.object.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("client.id") == "thisclientid"
        assert not mock_consumer.call_args[0][0].get("client.id") == socket.getfqdn()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_statistics_interval_can_be_overwritten(self, mock_consumer):
        self.object.shut_down()
        self.object._config.kafka_config["statistics.interval.ms"] = "999999999"
        self.object.setup()
        mock_consumer.assert_called()
        assert mock_consumer.call_args[0][0].get("statistics.interval.ms") == "999999999"
