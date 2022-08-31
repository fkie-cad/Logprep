# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import json
import os
import tempfile
from copy import deepcopy

import pytest

from logprep.connector.connector_factory import (
    InvalidConfigurationError,
    ConnectorFactory,
    UnknownConnectorTypeError,
)
from logprep.input.confluent_kafka_input import ConfluentKafkaInput
from logprep.input.dummy_input import DummyInput
from logprep.input.json_input import JsonInput
from logprep.input.jsonl_input import JsonlInput
from logprep.output.confluent_kafka_output import ConfluentKafkaOutput
from logprep.output.dummy_output import DummyOutput
from logprep.output.es_output import ElasticsearchOutput
from logprep.output.writing_output import WritingOutput


class TestConnectorFactory:
    def setup_class(self):
        self.configuration = {"type": "dummy", "input": [{}, {}]}

    def test_fails_to_create_a_connector_from_empty_config(self):
        with pytest.raises(InvalidConfigurationError, match="Connector type not specified"):
            ConnectorFactory.create({})

    def test_fails_to_create_a_connector_from_config_without_type_field(self):
        configuration_without_type = deepcopy(self.configuration)
        del configuration_without_type["type"]
        with pytest.raises(InvalidConfigurationError, match="Connector type not specified"):
            ConnectorFactory.create(configuration_without_type)

    def test_fails_to_create_a_connector_when_type_is_unknown(self):
        for unknown_type in ["test", "unknown", "this is not a known type"]:
            with pytest.raises(
                UnknownConnectorTypeError, match=f'Unknown connector type: "{unknown_type}"'
            ):
                ConnectorFactory.create({"type": unknown_type})

    def test_returns_an_input_and_output_instance(self):
        pass


class TestConnectorFactoryDummy:
    def setup_class(self):
        self.configuration = {"type": "dummy", "input": [{}, {}]}

    def test_fails_to_create_a_connector_when_input_is_missing(self):
        with pytest.raises(InvalidConfigurationError):
            ConnectorFactory.create({"type": "dummy"})

    def test_returns_a_dummy_input_and_output_instance(self):
        _input, output = ConnectorFactory.create(self.configuration)

        assert isinstance(_input, DummyInput)
        assert isinstance(output, DummyOutput)

        assert _input._documents == self.configuration["input"]


class TestConnectorFactoryWriter:
    def setup_class(self):
        _, self._temp_path = tempfile.mkstemp()
        with open(self._temp_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(json.dumps({"foo": "bar"}))
        self.configuration = {
            "type": "writer",
            "input_path": self._temp_path,
            "output_path": self._temp_path,
            "output_path_custom": self._temp_path,
        }

    def test_returns_a_writer_input_and_output_instance(self):
        jsonl_input, writing_output = ConnectorFactory.create(self.configuration)

        assert isinstance(jsonl_input, JsonlInput)
        assert isinstance(writing_output, WritingOutput)

        assert jsonl_input._documents == [{"foo": "bar"}]

    def teardown_class(self):
        os.remove(self._temp_path)


class TestConnectorFactoryWriterJsonInput:
    def setup_class(self):
        _, self._temp_path = tempfile.mkstemp()
        with open(self._temp_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(json.dumps({"foo": "bar"}))
        self.configuration = {
            "type": "writer_json_input",
            "input_path": self._temp_path,
            "output_path": self._temp_path,
            "output_path_custom": self._temp_path,
        }

    def test_returns_a_writer_input_and_output_instance(self):
        json_input, writing_output = ConnectorFactory.create(self.configuration)

        assert isinstance(json_input, JsonInput)
        assert isinstance(writing_output, WritingOutput)

        assert json_input._documents == [{"foo": "bar"}]

    def teardown_class(self):
        os.remove(self._temp_path)


class TestConnectorFactoryConfluentKafka:
    def setup_method(self):
        self.configuration = {
            "type": "confluentkafka",
            "bootstrapservers": ["bootstrap1:9092", "bootstrap2:9092"],
            "consumer": {
                "topic": "test_consumer",
                "group": "test_consumer_group",
                "auto_commit": True,
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
        expected_input = {
            "bootstrap.servers": "bootstrap1:9092,bootstrap2:9092",
            "group.id": "test_consumer_group",
            "enable.auto.commit": True,
            "enable.auto.offset.store": True,
            "session.timeout.ms": 6000,
            "default.topic.config": {"auto.offset.reset": "smallest"},
            "security.protocol": "SSL",
            "ssl.ca.location": "test_cafile",
            "ssl.certificate.location": "test_certificatefile",
            "ssl.key.location": "test_keyfile",
            "ssl.key.password": "test_password",
        }

        expected_output = {
            "bootstrap.servers": "bootstrap1:9092,bootstrap2:9092",
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

        cc_input, cc_output = ConnectorFactory.create(self.configuration)

        assert isinstance(cc_input, ConfluentKafkaInput)
        assert isinstance(cc_output, ConfluentKafkaOutput)

        assert cc_input._create_confluent_settings() == expected_input
        assert cc_output._create_confluent_settings() == expected_output


class TestConnectorFactoryConfluentKafkaES:
    def setup_class(self):
        self.configuration = {
            "type": "confluentkafka_es",
            "bootstrapservers": ["bootstrap1:9092", "bootstrap2:9092"],
            "consumer": {
                "topic": "test_consumer",
                "group": "test_consumer_group",
                "auto_commit": True,
                "enable_auto_offset_store": True,
            },
            "elasticsearch": {
                "hosts": "127.0.0.1:9200",
                "default_index": "default_index",
                "error_index": "error_index",
                "message_backlog": 10000,
                "timeout": 10000,
            },
            "ssl": {
                "cafile": "test_cafile",
                "certfile": "test_certificatefile",
                "keyfile": "test_keyfile",
                "password": "test_password",
            },
        }

    def test_creates_connector_with_expected_configuration(self):
        expected_input = {
            "bootstrap.servers": "bootstrap1:9092,bootstrap2:9092",
            "group.id": "test_consumer_group",
            "enable.auto.commit": True,
            "enable.auto.offset.store": True,
            "session.timeout.ms": 6000,
            "default.topic.config": {"auto.offset.reset": "smallest"},
            "security.protocol": "SSL",
            "ssl.ca.location": "test_cafile",
            "ssl.certificate.location": "test_certificatefile",
            "ssl.key.location": "test_keyfile",
            "ssl.key.password": "test_password",
        }

        cc_input, es_output = ConnectorFactory.create(self.configuration)

        assert isinstance(cc_input, ConfluentKafkaInput)
        assert isinstance(es_output, ElasticsearchOutput)

        assert cc_input._create_confluent_settings() == expected_input
