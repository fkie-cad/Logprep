"""This module contains a factory to create connectors and processors."""

from collections.abc import Sequence

from logprep.abc.component import Component
from logprep.configuration import Configuration
from logprep.factory_error import (
    InvalidConfigSpecificationError,
    InvalidConfigurationError,
)


class TrackedCreator:
    """Helper class for tracking created components"""

    def __init__(self) -> None:
        self._tracked_components: list[Component] = []

    def __enter__(self) -> "TrackedCreator":
        self._tracked_components = []
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tracked_components = []

    def create(self, configuration: dict) -> Component:
        """Create and record a component"""
        component = Factory.create(configuration)
        self._tracked_components.append(component)
        return component

    def __call__(self, configuration: dict) -> Component:
        return self.create(configuration)

    @property
    def components(self) -> Sequence[Component]:
        """Return created components up to this point"""
        return self._tracked_components


class Factory:
    """Create components for logprep."""

    @staticmethod
    def record() -> TrackedCreator:
        """Get an object for tracking created components"""
        return TrackedCreator()

    @staticmethod
    def create(configuration: dict) -> Component:
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
        # we know configuration has exactly one entry
        [(component_name, component_configuration_dict)] = configuration.items()
        if component_configuration_dict is None:
            raise InvalidConfigurationError(
                f'The definition of component "{component_name}" is empty.'
            )
        if not isinstance(component_configuration_dict, dict):
            raise InvalidConfigSpecificationError(component_name)
        component = Configuration.get_class(component_name, component_configuration_dict)
        component_configuration = Configuration.create(component_name, component_configuration_dict)
        return component(component_name, component_configuration)
