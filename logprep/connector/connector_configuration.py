"""module for connector configuration """
from typing import TYPE_CHECKING, Any, Mapping

from logprep.connector.connector_registry import ConnectorRegistry
from logprep.connector.connector_factory_error import (
    UnknownConnectorTypeError,
    NoTypeSpecifiedError,
)

if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc import Connector


class ConnectorConfiguration:
    """factory and adapter for generating config"""

    @classmethod
    def create(cls, name: str, config_: Mapping[str, Any]) -> "Connector.Config":
        """factory method to create processor configuration

        Parameters
        ----------
        name: str
            the name of the processor
        config_ : Mapping[str, Any]
            the config dict

        Returns
        -------
        Connector.Config
            the processor configuration
        """
        connector_class = cls.get_connector_class(name, config_)
        return connector_class.Config(**config_)

    @staticmethod
    def get_connector_class(name: str, config_: Mapping[str, Any]):
        """gets the processorclass from config

        Parameters
        ----------
        name : str
            The name of the processor
        config_ : Mapping[str, Any]
            the configuration with setted `type`

        Returns
        -------
        Connector
            The requested processor

        Raises
        ------
        UnknownConnectorTypeError
            if processor is not found
        NoTypeSpecifiedError
            if type is not found in config object
        """
        if "type" not in config_:
            raise NoTypeSpecifiedError(name)
        processors = ConnectorRegistry.mapping
        processor_type = config_.get("type")
        if processor_type not in processors:
            raise UnknownConnectorTypeError(processor_type)
        return ConnectorRegistry.get_connector_class(processor_type)
