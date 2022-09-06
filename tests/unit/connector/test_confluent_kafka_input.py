# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
from unittest import mock

import pytest

from logprep.abc.input import CriticalInputError
from tests.unit.connector.base import BaseInputTestCase
from tests.unit.connector.test_confluent_kafka_common import CommonConfluentKafkaTestCase


class TestConfluentKafkaInput(BaseInputTestCase, CommonConfluentKafkaTestCase):
    CONFIG = {
        "type": "confluentkafka_input",
        "bootstrapservers": ["testserver:9092"],
        "topic": "test_input_raw",
        "group": "test_consumergroup",
        "auto_commit": False,
        "session_timeout": 654321,
        "enable_auto_offset_store": True,
        "offset_reset_policy": "latest",
        "ssl": {
            "cafile": "test_cafile",
            "certfile": "test_certfile",
            "keyfile": "test_keyfile",
            "password": "test_password",
        },
    }

    def test_confluent_settings_contains_expected_values(self):
        expected_config = {
            "bootstrap.servers": "testserver:9092",
            "default.topic.config": {"auto.offset.reset": "latest"},
            "enable.auto.commit": False,
            "enable.auto.offset.store": True,
            "group.id": "test_consumergroup",
            "security.protocol": "SSL",
            "session.timeout.ms": 654321,
            "ssl.ca.location": "test_cafile",
            "ssl.certificate.location": "test_certfile",
            "ssl.key.location": "test_keyfile",
            "ssl.key.password": "test_password",
        }
        kafka_input_cfg = self.object._confluent_settings
        assert kafka_input_cfg == expected_config

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
            match=r"A confluent-kafka record contains an error code: "
            r"\(An arbitrary confluent-kafka error\)",
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
