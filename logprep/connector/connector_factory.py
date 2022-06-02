"""This module contains a connector factory for logprep and input/output communication."""

from typing import Tuple

from logprep.connector.confluent_kafka import ConfluentKafkaFactory
from logprep.connector.connector_factory_error import (
    UnknownConnectorTypeError,
    InvalidConfigurationError,
)
from logprep.input.input import Input
from logprep.output.output import Output
from logprep.input.dummy_input import DummyInput
from logprep.input.jsonl_input import JsonlInput
from logprep.input.json_input import JsonInput
from logprep.output.dummy_output import DummyOutput
from logprep.output.writing_output import WritingOutput


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
                confluent_kafka = ConfluentKafkaFactory.create_from_configuration(config)
                return confluent_kafka, confluent_kafka
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
