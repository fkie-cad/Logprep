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

    default_configuration = {
        "bootstrap.servers": "bootstrap1,bootstrap2",
        "group.id": "consumer_group",
        "enable.auto.commit": True,
        "enable.auto.offset.store": True,
        "session.timeout.ms": 6000,
        "default.topic.config": {"auto.offset.reset": "smallest"},
        "acks": "all",
        "compression.type": "none",
        "queue.buffering.max.messages": 31337,
        "linger.ms": 0,
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

    def test_create_confluent_settings_contains_expected_values(self):
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
        kafka_input_cfg = self.object._create_confluent_settings()
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

    # def test_update_default_configuration_overwrites_default_options_in_nested_field(self):
    #     default_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bar"}},
    #         "another": "option",
    #     }
    #     user_config = {"option": {"with": {"foo": "bi"}}}
    #     expected_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bi"}},
    #         "another": "option",
    #     }
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     new_config = kafka._set_connector_type_options(user_config, default_config)
    #     assert new_config == expected_config

    # def test_update_default_configuration_overwrites_default_options_in_first_level(self):
    #     default_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bar"}},
    #         "another": "option",
    #     }
    #     user_config = {"another": "test option"}
    #     expected_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bar"}},
    #         "another": "test option",
    #     }
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     new_config = kafka._set_connector_type_options(user_config, default_config)
    #     assert new_config == expected_config

    # def test_update_default_configuration_raises_error_on_unknown_option_in_first_level(self):
    #     default_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bar"}},
    #         "another": "option",
    #     }
    #     user_config = {"unknown": "option"}
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     with pytest.raises(UnknownOptionError, match="Unknown Option: unknown"):
    #         _ = kafka._set_connector_type_options(user_config, default_config)

    # def test_update_default_configuration_does_nothing_on_empty_user_configs(self):
    #     default_config = {
    #         "option": {"with": {"multiple": "layers", "foo": "bar"}},
    #         "another": "option",
    #     }
    #     user_config = {}
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     new_config = kafka._set_connector_type_options(user_config, default_config)
    #     assert new_config == default_config

    # def test_update_default_configuration_raises_error_on_wrong_type(self):
    #     default_config = {
    #         "option": 12.2,
    #         "another": "option",
    #     }
    #     user_config = {"option": "string and not float"}
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     with pytest.raises(
    #         UnknownOptionError,
    #         match="Wrong Option type for 'string and not float'. "
    #         "Got <class 'str'>, expected <class 'float'>.",
    #     ):
    #         _ = kafka._set_connector_type_options(user_config, default_config)

    # @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    # def test_shut_down_calls_consumer_close(self, _):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     kafka._create_consumer()
    #     kafka_consumer = kafka._consumer
    #     kafka.shut_down()
    #     kafka_consumer.close.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    # def test_shut_down_sets_consumer_to_none(self, _):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
    #     kafka._create_consumer()
    #     kafka.shut_down()
    #     assert kafka._consumer is None

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_store_custom_calls_producer_flush_on_buffererror(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka._producer.produce = mock.MagicMock()
    #     kafka._producer.produce.side_effect = BufferError
    #     kafka._producer.flush = mock.MagicMock()
    #     kafka.store_custom({"message": "does not matter"}, "doesnotcare")
    #     kafka._producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_store_failed_calls_producer_flush_on_buffererror(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka._producer.produce = mock.MagicMock()
    #     kafka._producer.produce.side_effect = BufferError
    #     kafka._producer.flush = mock.MagicMock()
    #     kafka.store_failed(
    #         "doesnotcare", {"message": "does not matter"}, {"message": "does not matter"}
    #     )
    #     kafka._producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_shut_down_calls_producer_flush(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka.shut_down()
    #     mock_producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_shut_down_sets_producer_to_none(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka.shut_down()
    #     assert kafka._producer is None
