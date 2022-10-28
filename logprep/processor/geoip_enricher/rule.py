"""This module is used to resolve field values from documents via a list."""

import warnings
from attrs import define, field, validators


from logprep.processor.base.rule import SourceTargetRule
from logprep.util.helper import add_and_overwrite, pop_dotted_field_value


class GeoipEnricherRule(SourceTargetRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(SourceTargetRule.Config):
        """RuleConfig for GeoipEnricher"""

        target_field: str = field(validator=validators.instance_of(str), default="geoip")

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("geoip_enricher", {}).get("source_ip") is not None:
            source_field_value = pop_dotted_field_value(rule, "geoip_enricher.source_ip")
            add_and_overwrite(rule, "geoip_enricher.source_fields", [source_field_value])
            warnings.warn(
                (
                    "geoip_enricher.source_ip is deprecated. "
                    "Use geoip_enricher.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("geoip_enricher", {}).get("output_field") is not None:
            target_field_value = pop_dotted_field_value(rule, "geoip_enricher.output_field")
            add_and_overwrite(rule, "geoip_enricher.target_field", target_field_value)
            warnings.warn(
                (
                    "geoip_enricher.output_field is deprecated. "
                    "Use geoip_enricher.target_field instead"
                ),
                DeprecationWarning,
            )
