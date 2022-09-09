"""module for component configuration """
from typing import TYPE_CHECKING, Any, Mapping

from logprep.registry import Registry
from logprep.factory_error import (
    NoTypeSpecifiedError,
    UnknownComponentTypeError,
)

if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc import Component


class Configuration:
    """factory and adapter for generating config"""

    @classmethod
    def create(cls, name: str, config_: Mapping[str, Any]) -> "Component.Config":
        """factory method to create component configuration

        Parameters
        ----------
        name: str
            the name of the pipeline component
        config_ : Mapping[str, Any]
            the config dict

        Returns
        -------
        Config
            the pipeline component configuration
        """
        class_ = cls.get_class(name, config_)
        return class_.Config(**config_)

    @staticmethod
    def get_class(name: str, config_: Mapping[str, Any]):
        """gets the class from config

        Parameters
        ----------
        name : str
            The name of the component
        config_ : Mapping[str, Any]
            the configuration with setted `type`

        Returns
        -------
        Processor|Connector
            The requested pipeline component

        Raises
        ------
        UnknownProcessorTypeError
            if component is not found
        NoTypeSpecifiedError
            if type is not found in config object
        """
        if "type" not in config_:
            raise NoTypeSpecifiedError(name)
        components = Registry.mapping
        component_type = config_.get("type")
        if component_type not in components:
            raise UnknownComponentTypeError(component_type)
        return Registry.get_class(component_type)
