"""This module contains all ConnectorFactory related exceptions."""


class ConnectorFactoryError(BaseException):
    """Base class for ConnectorFactory related exceptions."""


class InvalidConfigurationError(ConnectorFactoryError):
    """Raise if the configuration is invalid."""


class NotExactlyOneEntryInConfigurationError(InvalidConfigurationError):
    """Raise if there is not exactly one processor definition per pipeline."""

    def __init__(self):
        super().__init__("There must be exactly one known connector definition.")


class InvalidConfigSpecificationError(InvalidConfigurationError):
    """Raise if the processor configuration was not specified as an object."""

    def __init__(self):
        super().__init__("The connector configuration must be specified as an object.")


class UnknownConnectorTypeError(ConnectorFactoryError):
    """Raise if the connector type is unknown."""

    def __init__(self, connector_type):
        super().__init__(f'Unknown connector type: "{connector_type}"')


class NoTypeSpecifiedError(InvalidConfigurationError):
    """Raise if the processor type specification is missing."""

    def __init__(self, processor_name=None):
        message = "The processor type specification is missing"
        if processor_name:
            message += f" for processor with name '{processor_name}'"
        super().__init__(message)
