from copy import deepcopy

from pytest import raises

from logprep.connector.confluent_kafka import ConfluentKafka
from logprep.connector.connector_factory import (
    InvalidConfigurationError,
    ConnectorFactory,
    UnknownConnectorTypeError,
)
from logprep.input.dummy_input import DummyInput
from logprep.output.dummy_output import DummyOutput


class TestConnectorFactory:
    def setup_class(self):
        self.configuration = {"type": "dummy", "input": [{}, {}]}

    def test_fails_to_create_a_connector_from_empty_config(self):
        with raises(InvalidConfigurationError, match="Connector type not specified"):
            ConnectorFactory.create({})

    def test_fails_to_create_a_connector_from_config_without_type_field(self):
        configuration_without_type = deepcopy(self.configuration)
        del configuration_without_type["type"]
        with raises(InvalidConfigurationError, match="Connector type not specified"):
            ConnectorFactory.create(configuration_without_type)

    def test_fails_to_create_a_connector_when_type_is_unknown(self):
        for unknown_type in ["test", "unknown", "this is not a known type"]:
            with raises(
                UnknownConnectorTypeError, match='Unknown connector type: "%s"' % unknown_type
            ):
                ConnectorFactory.create({"type": unknown_type})

    def test_returns_an_input_and_output_instance(self):
        pass


class TestConnectorFactoryDummy:
    def setup_class(self):
        self.configuration = {"type": "dummy", "input": [{}, {}]}

    def test_fails_to_create_a_connector_when_input_is_missing(self):
        with raises(InvalidConfigurationError):
            ConnectorFactory.create({"type": "dummy"})

    def test_returns_a_dummy_input_and_output_instance(self):
        input, output = ConnectorFactory.create(self.configuration)

        assert isinstance(input, DummyInput)
        assert isinstance(output, DummyOutput)

        assert input._documents == self.configuration["input"]


class TestConnectorFactoryConfluentKafka:
    def setup_class(self):
        self.configuration = {
            "type": "confluentkafka",
            "bootstrapservers": ["bootstrap1:9092", "bootstrap2:9092"],
            "consumer": {
                "topic": "test_consumer",
                "group": "test_consumer_group",
                "enable_auto_offset_store": True,
            },
            "producer": {
                "topic": "test_producer",
                "error_topic": "test_error_producer",
                "maximum_backlog": 31337,
            },
            "ssl": {
                "cafile": "test_cafile",
                "certfile": "test_certificatefile",
                "keyfile": "test_keyfile",
                "password": "test_password",
            },
        }

    def test_creates_connector_with_expected_configuration(self):
        expected = {
            "bootstrap.servers": "bootstrap1:9092,bootstrap2:9092",
            "group.id": "test_consumer_group",
            "enable.auto.commit": True,
            "enable.auto.offset.store": True,
            "session.timeout.ms": 6000,
            "default.topic.config": {"auto.offset.reset": "smallest"},
            "acks": "all",
            "compression.type": "none",
            "queue.buffering.max.messages": 31337,
            "linger.ms": 0,
            "security.protocol": "SSL",
            "ssl.ca.location": "test_cafile",
            "ssl.certificate.location": "test_certificatefile",
            "ssl.key.location": "test_keyfile",
            "ssl.key.password": "test_password",
        }

        input, output = ConnectorFactory.create(self.configuration)

        assert isinstance(input, ConfluentKafka)
        assert isinstance(output, ConfluentKafka)
        assert input == output

        assert input._create_confluent_settings() == expected
