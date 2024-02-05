"""This module contains errors related to ProcessorFactory."""

from logprep.abc.exceptions import LogprepException


class FactoryError(LogprepException):
    """Base class for ProcessorFactory related exceptions."""


class InvalidConfigurationError(FactoryError):
    """Raise if configuration is invalid."""


class InvalidConfigSpecificationError(InvalidConfigurationError):
    """Raise if the configuration was not specified as an object."""

    def __init__(self, component=None):
        if component:
            super().__init__(
                f'The configuration for component "{component}" must be specified as an object.'
            )
        else:
            super().__init__("The configuration must be specified as an object.")


class NoTypeSpecifiedError(InvalidConfigurationError):
    """Raise if the type specification is missing."""

    def __init__(self, name=None):
        message = "The type specification is missing"
        if name:
            message += f" for element with name '{name}'"
        super().__init__(message)


class UnknownComponentTypeError(FactoryError):
    """Raise if the type is unknown."""

    def __init__(self, component_name, component_type):
        super().__init__(f"Unknown type '{component_type}' for '{component_name}'")
