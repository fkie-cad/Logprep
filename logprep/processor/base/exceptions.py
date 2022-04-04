"""This module contains exceptions for rules."""

from typing import Any

from logprep.processor.processor_factory_error import InvalidConfigurationError


class RuleError(BaseException):
    """Base class for Rule related exceptions."""


class InvalidRuleDefinitionError(RuleError):
    """Raise if defined rule is invalid."""

    def __init__(self, message: str = None):
        if message:
            super().__init__(message)


class MismatchedRuleDefinitionError(RuleError):
    """Raise if defined rule does not conform to schema."""


class NotARulesDirectoryError(RuleError):
    """Raise if path is not a rules directory."""

    def __init__(self, name: str, path: str):
        super().__init__(name, f'Not a rule directory: "{path}"')


class InvalidRuleFileError(InvalidConfigurationError):
    """Raise if rule file at path is invalid."""

    def __init__(self, name: str, path: str, message: str = ""):
        if message:
            super().__init__(name, f'Invalid rule file "{path}": {message}')
        else:
            super().__init__(name, f'Invalid rule file "{path}".')


class InvalidRuleConfigurationError(InvalidConfigurationError):
    """Raise if rule configuration is invalid."""


class KeyDoesnotExistInSchemaError(MismatchedRuleDefinitionError):
    """Raise if key in defined rule does not conform to schema."""

    def __init__(self, key: str):
        super().__init__(f"Invalid key '{key}'.")


class ValueDoesnotExistInSchemaError(MismatchedRuleDefinitionError):
    """Raise if value in defined rule does not conform to schema."""

    def __init__(self, key: str, value: Any):
        super().__init__(f"Invalid value '{value}' for key '{key}'.")
