"""This module is used to extract date times and split them into multiple fields."""
import warnings
from attrs import define, field, fields

from logprep.processor.base.rule import Rule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DatetimeExtractorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config für the DatetimeExtractorRule"""

        source_fields: list = field(validator=fields(Rule.Config).source_fields.validator)
        target_field: list = field(validator=fields(Rule.Config).target_field.validator)

    @property
    def datetime_field(self) -> str:
        """Returns the datetime_field"""
        return self._config.source_fields[0]

    @property
    def destination_field(self) -> str:
        """Returns the field"""
        return self._config.target_field

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("datetime_extractor", {}).get("datetime_field") is not None:
            source_field_value = pop_dotted_field_value(rule, "datetime_extractor.datetime_field")
            add_and_overwrite(rule, "datetime_extractor.source_fields", [source_field_value])
            warnings.warn(
                (
                    "datetime_extractor.datetime_field is deprecated. "
                    "Use datetime.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("datetime_extractor", {}).get("destination_field") is not None:
            target_field_value = pop_dotted_field_value(
                rule, "datetime_extractor.destination_field"
            )
            add_and_overwrite(rule, "datetime_extractor.target_field", target_field_value)
            warnings.warn(
                (
                    "datetime_extractor.destination_field is deprecated. "
                    "Use datetime.target_field instead"
                ),
                DeprecationWarning,
            )
