"""This module is used to resolve field values from documents via a list."""

from attrs import define, field, validators


from logprep.processor.base.rule import Rule


class GeoipEnricherRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for GeoipEnricher"""

        source_ip: str = field(validator=validators.instance_of(str))
        output_field: str = field(validator=validators.instance_of(str), default="geoip")

    @property
    def source_ip(self) -> dict:
        """Returns the source IP"""
        return self._config.source_ip

    @property
    def output_field(self) -> str:
        """Returns the output field"""
        return self._config.output_field
