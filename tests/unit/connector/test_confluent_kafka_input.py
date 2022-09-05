# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
from copy import deepcopy
from socket import getfqdn
from unittest import mock

import pytest

from logprep.abc.input import CriticalInputError
from logprep.connector.connector_factory import ConnectorFactory
from logprep.processor.processor_factory_error import InvalidConfigurationError
from tests.unit.connector.base import BaseInputTestCase


class TestConfluentKafkaInput(BaseInputTestCase):
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

    def test_client_id_is_set_to_hostname(self):
        assert self.object._client_id == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unkown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_wrong_type_in_ssl_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"ssl": "this should not be a string"})
        with pytest.raises(TypeError, match=r"'ssl' must be <class 'dict'>"):
            _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_incomplete_ssl_options(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.get("ssl", {}).pop("password")
        with pytest.raises(
            InvalidConfigurationError, match=r"following keys are missing: {'password'}"
        ):
            _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_extra_key_in_ssl_options(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.get("ssl", {}).update({"extra_key": "value"})
        with pytest.raises(
            InvalidConfigurationError, match=r"following keys are unknown: {'extra_key'}"
        ):
            _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_without_ssl_options_and_set_defaults(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.pop("ssl")
        kafka_input = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        assert kafka_input._config.ssl == {
            "cafile": None,
            "certfile": None,
            "keyfile": None,
            "password": None,
        }

    def test_create_fails_for_unknown_offset_reset_policy(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"offset_reset_policy": "invalid"})
        with pytest.raises(ValueError, match=r"'offset_reset_policy' must be in.*got 'invalid'"):
            _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)

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
