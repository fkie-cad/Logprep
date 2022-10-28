"""This module is used to resolve domains."""

from attrs import define, field, validators
from logprep.processor.base.rule import Rule


class DomainResolverRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for DomainResolver"""

        source_url_or_domain: str = field(validator=validators.instance_of(str))
        output_field: str = field(validator=validators.instance_of(str), default="resolved_ip")

    @property
    def source_url_or_domain(self) -> str:
        """Returns the source_url_or_domain"""
        return self._config.source_url_or_domain

    @property
    def output_field(self) -> str:
        """Returns the output_field"""
        return self._config.output_field
