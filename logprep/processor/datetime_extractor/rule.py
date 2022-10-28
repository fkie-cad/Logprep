"""This module is used to extract date times and split them into multiple fields."""
import warnings
from logprep.processor.base.rule import SourceTargetRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DatetimeExtractorRule(SourceTargetRule):
    """Check if documents match a filter."""

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("datetime_extractor", {}).get("datetime_field") is not None:
            source_field_value = pop_dotted_field_value(rule, "datetime_extractor.datetime_field")
            add_and_overwrite(rule, "datetime_extractor.source_fields", [source_field_value])
            warnings.warn(
                (
                    "datetime_extractor.datetime_field is deprecated. "
                    "Use datetime_extractor.source_fields instead"
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
                    "Use datetime_extractor.target_field instead"
                ),
                DeprecationWarning,
            )
