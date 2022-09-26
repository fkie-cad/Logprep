"""This module contains a factory to create connectors and processors."""
import copy
from typing import TYPE_CHECKING

from logprep.abc import Connector
from logprep.configuration import Configuration
from logprep.factory_error import (
    InvalidConfigSpecificationError,
    InvalidConfigurationError,
    NotExactlyOneEntryInConfigurationError,
)

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


class Factory:
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
