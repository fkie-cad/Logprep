"""This module contains errors related to ProcessorFactory."""


class FactoryError(BaseException):
    """Base class for ProcessorFactory related exceptions."""


class InvalidConfigurationError(FactoryError):
    """Raise if configuration is invalid."""


class NotExactlyOneEntryInConfigurationError(InvalidConfigurationError):
    """Raise if there is not exactly one definition per pipeline."""

    def __init__(self):
        super().__init__("There must be exactly one definition per pipeline entry.")


class InvalidConfigSpecificationError(InvalidConfigurationError):
    """Raise if the configuration was not specified as an object."""

    def __init__(self):
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

    def __init__(self, processor_type):
        super().__init__(f"Unknown type '{processor_type}'")
