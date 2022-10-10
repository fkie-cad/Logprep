"""
This module is used to split domains in a given field into it's corresponding labels/parts.
"""

from ruamel.yaml import YAML
from attrs import define, field, validators
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class DomainLabelExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for DomainLabelExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"DomainLabelExtractor rule ({message})")


class InvalidDomainLabelExtractorDefinition(DomainLabelExtractorRuleError):
    """Raise if DomainLabelExtractor definition invalid."""

    def __init__(self, definition):
        message = f"The following DomainLabelExtractor definition is invalid: {definition}"
        super().__init__(message)


class DomainLabelExtractorRule(Rule):
    """Check if documents match a filter."""

    @define
    class Config(Rule.Config):
        """DomainLabelExtractorRule Config"""

        target_field: str = field(validator=validators.instance_of(str))
        output_field: str = field(validator=validators.instance_of(str))

    @property
    def target_field(self) -> str:
        """Returns the target_field"""
        return self._config.target_field

    @property
    def output_field(self) -> str:
        """Returns the output_field"""
        return self._config.output_field
