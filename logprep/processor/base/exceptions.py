"""This module contains exceptions for rules."""

from typing import TYPE_CHECKING, Any, List

from logprep.factory_error import FactoryError

if TYPE_CHECKING:
    from logprep.abc.processor import Processor
    from logprep.processor.base.rule import Rule


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


class SkipImportError(FactoryError):
    """Raise if the processor type can't be imported."""

    def __init__(self, processor_type=None):  # pragma: no cover
        if processor_type:
            super().__init__(f"Processor type '{processor_type}' can't be imported")
        else:
            super().__init__("Processor can't be imported")


class ProcessingError(Exception):
    """Base class for exceptions related to processing events."""

    def __init__(self, processor: "Processor", message: str):
        super().__init__(f"{self.__class__.__name__} in {processor.describe()}: {message}")


class ProcessingCriticalError(ProcessingError):
    """A critical error occurred - stop processing of this event"""

    def __init__(self, processor: "Processor", message: str, event: dict):
        event.clear()
        processor.metrics.number_of_errors += 1
        super().__init__(processor, f"{message} -> event was deleted")


class ProcessingWarning(Warning):
    """A minor error occurred - log the error, but continue processing the event."""

    def __init__(self, processor: "Processor", message: str, rule: "Rule", event: dict):
        processor.metrics.number_of_warnings += 1
        message = f"""{message}
Rule: {rule},
Event: {event}
        """
        super().__init__(f"{self.__class__.__name__} in {processor.describe()}: {message}")


class FieldExistsWarning(ProcessingWarning):
    """Raised if field already exists."""

    def __init__(
        self,
        processor: "Processor",
        rule: "Rule",
        event: dict,
        skipped_fields: List[str],
    ):
        message = (
            "The following fields could not be written, because "
            "one or more subfields existed and could not be extended: "
            f"{', '.join(skipped_fields)}"
        )
        super().__init__(processor, message, rule, event)
