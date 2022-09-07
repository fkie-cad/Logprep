"""This module contains a factory to create connectors."""
import copy
from typing import TYPE_CHECKING

from logprep.abc import Connector
from logprep.configuration import Configuration
from logprep.factory_error import (
    InvalidConfigSpecificationError,
    InvalidConfigurationError,
    NotExactlyOneEntryInConfigurationError,
)
from logprep.abc.input import Input
from logprep.abc.output import Output
from logprep.connector.dummy.input import DummyInput
from logprep.connector.jsonl.input import JsonlInput
from logprep.connector.json.input import JsonInput
from logprep.connector.confluent_kafka.input import (
    ConfluentKafkaInput,
    ConfluentKafkaInputFactory,
)
from logprep.connector.dummy.output import DummyOutput
from logprep.connector.jsonl.output import JsonlOutput
from logprep.connector.elasticsearch.output import (
    ElasticsearchOutput,
    ElasticsearchOutputFactory,
)
from logprep.connector.opensearch.output import (
    OpenSearchOutput,
    OpenSearchOutputFactory,
)
from logprep.connector.confluent_kafka.output import (
    ConfluentKafkaOutput,
    ConfluentKafkaOutputFactory,
)


class PipelineComponentFactory:
    """Create components for logprep."""

    @classmethod
    def create(cls, configuration: dict, logger: "Logger") -> Connector:
        """Create connector."""
        if not configuration:
            raise NotExactlyOneEntryInConfigurationError()
        if len(configuration) > 1:
            raise InvalidConfigurationError(
                "There must be exactly one definition per pipeline entry."
            )
        for connector_name, connector_configuration_dict in configuration.items():
            if not isinstance(connector_configuration_dict, dict):
                raise InvalidConfigSpecificationError()
            metric_labels = {}
            if "metric_labels" in configuration[connector_name]:
                metric_labels = configuration[connector_name].pop("metric_labels")
            connector = Configuration.get_class(connector_name, connector_configuration_dict)
            connector_configuration = Configuration.create(
                connector_name, connector_configuration_dict
            )
            connector_configuration.metric_labels = copy.deepcopy(metric_labels)
            return connector(connector_name, connector_configuration, logger)
