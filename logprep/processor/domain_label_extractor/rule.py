"""
This module is used to split domains in a given field into it's corresponding labels/parts.
"""
import warnings

from logprep.processor.base.rule import SimpleSourceTargetRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DomainLabelExtractorRule(SimpleSourceTargetRule):
    """Check if documents match a filter."""

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("domain_label_extractor", {}).get("output_field") is not None:
            source_field_value = pop_dotted_field_value(rule, "domain_label_extractor.target_field")
            if source_field_value is not None:
                add_and_overwrite(
                    rule, "domain_label_extractor.source_fields", [source_field_value]
                )
                warnings.warn(
                    (
                        "domain_label_extractor.target_field is deprecated. "
                        "Use domain_label_extractor.source_fields instead"
                    ),
                    DeprecationWarning,
                )
            target_field_value = pop_dotted_field_value(rule, "domain_label_extractor.output_field")
            add_and_overwrite(rule, "domain_label_extractor.target_field", target_field_value)
            warnings.warn(
                (
                    "domain_label_extractor.output_field is deprecated. "
                    "Use domain_label_extractor.target_field instead"
                ),
                DeprecationWarning,
            )
