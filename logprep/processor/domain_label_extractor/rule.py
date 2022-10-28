"""
This module is used to split domains in a given field into it's corresponding labels/parts.
"""

from attrs import define, field, validators
from logprep.processor.base.rule import Rule


class DomainLabelExtractorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
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
