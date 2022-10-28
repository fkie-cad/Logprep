"""This module is used to extract date times and split them into multiple fields."""
from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class DatetimeExtractorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for DateTimeExtractor"""

        datetime_field: str = field(validator=validators.instance_of(str))
        destination_field: str = field(validator=validators.instance_of(str))

    @property
    def datetime_field(self) -> str:
        """Returns the datetime_field"""
        return self._config.datetime_field

    @property
    def destination_field(self) -> str:
        """Returns the field"""
        return self._config.destination_field
