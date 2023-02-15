"""This module contains a factory to create connectors and processors."""
import copy
from typing import TYPE_CHECKING

from logprep.abc.component import Component
from logprep.configuration import Configuration
from logprep.factory_error import (
    InvalidConfigSpecificationError,
    InvalidConfigurationError,
)

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


class Factory:
    """Create components for logprep."""

    @classmethod
    def create(cls, configuration: dict, logger: "Logger") -> Component:
        """Create component."""
        if configuration == {} or configuration is None:
            raise InvalidConfigurationError("The component definition is empty.")
        if not isinstance(configuration, dict):
            raise InvalidConfigSpecificationError()
        if len(configuration) > 1:
            raise InvalidConfigurationError(
                f"Found multiple component definitions ({', '.join(configuration.keys())}),"
                + " but there must be exactly one."
            )
        for component_name, component_configuration_dict in configuration.items():
            if configuration == {} or component_configuration_dict is None:
                raise InvalidConfigurationError(
                    f'The definition of component "{component_name}" is empty.'
                )
            if not isinstance(component_configuration_dict, dict):
                raise InvalidConfigSpecificationError(component_name)
            metric_labels = {}
            if "metric_labels" in configuration[component_name]:
                metric_labels = configuration[component_name].pop("metric_labels")
            component = Configuration.get_class(component_name, component_configuration_dict)
            component_configuration = Configuration.create(
                component_name, component_configuration_dict
            )
            component_configuration.metric_labels = copy.deepcopy(metric_labels)
            return component(component_name, component_configuration, logger)
