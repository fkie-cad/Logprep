"""This module contains all ConnectorFactory related exceptions."""


class ConnectorFactoryError(BaseException):
    """Base class for ConnectorFactory related exceptions."""


class InvalidConfigurationError(ConnectorFactoryError):
    """Raise if the configuration is invalid."""


class UnknownConnectorTypeError(ConnectorFactoryError):
    """Raise if the connector type is unknown."""
