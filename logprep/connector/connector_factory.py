"""This module contains a connector factory for logprep and input/output communication."""

from typing import Tuple

from logprep.connector.connector_factory_error import (
    UnknownConnectorTypeError,
    InvalidConfigurationError,
)
from logprep.abc.input import Input
from logprep.output.output import Output
from logprep.connector.dummy.input import DummyInput
from logprep.connector.jsonl.input import JsonlInput
from logprep.connector.json.input import JsonInput
from logprep.connector.confluent_kafka.input import (
    ConfluentKafkaInput,
    ConfluentKafkaInputFactory,
)
from logprep.connector.dummy.output import DummyOutput
from logprep.output.writing_output import WritingOutput
from logprep.output.es_output import ElasticsearchOutput, ElasticsearchOutputFactory
from logprep.connector.confluent_kafka.output import (
    ConfluentKafkaOutput,
    ConfluentKafkaOutputFactory,
)


class ConnectorFactory:
    """Create connectors for logprep and input/output communication."""

    @staticmethod
    def create(config: dict) -> Tuple[Input, Output]:
        """Create a connector based on the configured type.

        Parameters
        ----------
        config : dict
           Parsed configuration YML.

        Returns
        -------
        input : Input
            Source of incoming log data.
        output : Output
            Destination for processed outgoing log data.

        Raises
        ------
        UnknownConnectorTypeError
            If 'configuration['type']' is set to an unknown type.
        logprep.connector.connector_factory_error.InvalidConfigurationError
            If 'configuration['type']' is not specified.

        """
        try:
            if config["type"].lower() == "dummy":
                return ConnectorFactory._create_dummy_connector(config)
            if config["type"].lower() == "writer":
                return ConnectorFactory._create_writing_connector(config)
            if config["type"].lower() == "writer_json_input":
                return ConnectorFactory._create_writing_json_input_connector(config)
            if config["type"].lower() == "confluentkafka":
                kafka_input, kafka_output = ConnectorFactory._create_kafka_connector(config)
                return kafka_input, kafka_output
            if config["type"].lower() == "confluentkafka_es":
                kafka_input, es_output = ConnectorFactory._create_kafka_es_connector(config)
                return kafka_input, es_output
            raise UnknownConnectorTypeError('Unknown connector type: "{}"'.format(config["type"]))
        except KeyError:
            raise InvalidConfigurationError("Connector type not specified")

    @staticmethod
    def _create_dummy_connector(config: dict) -> Tuple[DummyInput, DummyOutput]:
        output_exceptions = config["output"] if "output" in config else []
        return DummyInput(config["input"]), DummyOutput(output_exceptions)

    @staticmethod
    def _create_writing_connector(config: dict) -> Tuple[JsonlInput, WritingOutput]:
        return JsonlInput(config["input_path"]), WritingOutput(
            config["output_path"],
            config.get("output_path_custom", None),
            config.get("output_path_errors", None),
        )

    @staticmethod
    def _create_writing_json_input_connector(config: dict) -> Tuple[JsonInput, WritingOutput]:
        return JsonInput(config["input_path"]), WritingOutput(
            config["output_path"],
            config.get("output_path_custom", None),
            config.get("output_path_errors", None),
        )

    @staticmethod
    def _create_kafka_connector(config: dict) -> Tuple[ConfluentKafkaInput, ConfluentKafkaOutput]:
        kafka_in = ConfluentKafkaInputFactory.create_from_configuration(config)
        kafka_out = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka_out.connect_input(kafka_in)
        kafka_in.connect_output(kafka_out)
        return kafka_in, kafka_out

    @staticmethod
    def _create_kafka_es_connector(config: dict) -> Tuple[ConfluentKafkaInput, ElasticsearchOutput]:
        kafka_in = ConfluentKafkaInputFactory.create_from_configuration(config)
        es_out = ElasticsearchOutputFactory.create_from_configuration(config)
        es_out.connect_input(kafka_in)
        kafka_in.connect_output(es_out)
        return kafka_in, es_out
