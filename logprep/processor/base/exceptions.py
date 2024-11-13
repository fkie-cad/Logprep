"""This module contains exceptions for rules."""

from typing import TYPE_CHECKING, Any, List

from logprep.abc.exceptions import LogprepException
from logprep.factory_error import FactoryError

if TYPE_CHECKING:  # pragma: no cover
    from logprep.processor.base.rule import Rule


class RuleError(LogprepException):
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


class ProcessingError(LogprepException):
    """Base class for exceptions related to processing events."""

    def __init__(self, message: str, rule: "Rule"):
        rule.metrics.number_of_errors += 1
        super().__init__(f"{self.__class__.__name__}: {message}")


class ProcessingCriticalError(ProcessingError):
    """A critical error occurred - stop processing of this event"""

    def __init__(self, message: str, rule: "Rule"):
        message = f"'{message}' -> rule.id: '{rule.id}'"
        full_message = f"{message} -> event was send to error output and further processing stopped"
        super().__init__(f"{self.__class__.__name__}: {full_message}", rule)
        self.message = message


class ProcessingWarning(Warning):
    """A warning occurred - log the warning, but continue processing the event."""

    def __init__(self, message: str, rule: "Rule | None", event: dict, tags: List[str] = None):
        self.tags = tags if tags else []
        if rule:
            rule.metrics.number_of_warnings += 1
            message += f", {rule.id=}, {rule.description=}"
        message += f", {event=}"
        super().__init__(f"{self.__class__.__name__}: {message}")


class FieldExistsWarning(ProcessingWarning):
    """Raised if field already exists."""

    def __init__(self, rule: "Rule | None", event: dict, skipped_fields: List[str]):
        self.skipped_fields = skipped_fields
        message = (
            "The following fields could not be written, because "
            "one or more subfields existed and could not be extended: "
            f"{', '.join(skipped_fields)}"
        )
        super().__init__(message, rule, event)
