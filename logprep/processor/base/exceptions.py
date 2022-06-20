"""This module contains exceptions for rules."""

from typing import Any

from logprep.processor.processor_factory_error import ProcessorFactoryError


class RuleError(BaseException):
    """Base class for Rule related exceptions."""


class InvalidRuleDefinitionError(RuleError):
    """Raise if defined rule is invalid."""

    def __init__(self, message: str = None):
        if message:
            super().__init__(message)


class MismatchedRuleDefinitionError(RuleError):
    """Raise if defined rule does not conform to schema."""


class KeyDoesnotExistInSchemaError(MismatchedRuleDefinitionError):
    """Raise if key in defined rule does not conform to schema."""

    def __init__(self, key: str):
        super().__init__(f"Invalid key '{key}'.")


class ValueDoesnotExistInSchemaError(MismatchedRuleDefinitionError):
    """Raise if value in defined rule does not conform to schema."""

    def __init__(self, key: str, value: Any):
        super().__init__(f"Invalid value '{value}' for key '{key}'.")


class SkipImportError(ProcessorFactoryError):
    """Raise if the processor type can't be imported."""

    def __init__(self, processor_type=None):  # pragma: no cover
        if processor_type:
            super().__init__(f"Processor type '{processor_type}' can't be imported")
        else:
            super().__init__("Processor can't be imported")


class ProcessingError(BaseException):
    """Base class for exceptions related to processing events."""

    def __init__(self, name: str, message: str):
        super().__init__(f"{name}: ({message})")


class ProcessingWarning(ProcessingError):
    """An minor error occurred - log the error but continue processing the event."""

    def __init__(self, message: str):
        super().__init__("ProcessingWarning", message)


class ProcessingWarningCollection(ProcessingError):
    """A collection of ProcessingWarnings."""

    def __init__(self, name: str, message: str, processing_warnings):
        super().__init__(name, message)
        self.processing_warnings = processing_warnings
