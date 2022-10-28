"""This module is used to resolve domains."""
import warnings
from attrs import define, field, fields
from logprep.processor.base.rule import SimpleSourceTargetRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DomainResolverRule(SimpleSourceTargetRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(SimpleSourceTargetRule.Config):
        """RuleConfig for DomainResolver"""

        target_field: list = field(
            validator=fields(SimpleSourceTargetRule.Config).target_field.validator,
            default="resolved_ip",
        )

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("domain_resolver", {}).get("source_url_or_domain") is not None:
            source_field_value = pop_dotted_field_value(
                rule, "domain_resolver.source_url_or_domain"
            )
            add_and_overwrite(rule, "domain_resolver.source_fields", [source_field_value])
            warnings.warn(
                (
                    "domain_resolver.source_url_or_domain is deprecated. "
                    "Use datetime.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("domain_resolver", {}).get("output_field") is not None:
            target_field_value = pop_dotted_field_value(rule, "domain_resolver.output_field")
            add_and_overwrite(rule, "domain_resolver.target_field", target_field_value)
            warnings.warn(
                (
                    "domain_resolver.output_field is deprecated. "
                    "Use datetime.target_field instead"
                ),
                DeprecationWarning,
            )
