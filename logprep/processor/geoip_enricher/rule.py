"""
Geoip Enricher
==============

The geoip enricher requires the additional field :code:`geoip`.
The default output_field can be overridden using the optional parameter
:code:`target_field`. This can be a dotted subfield.
The additional field :code:`geoip.source_fields` must be given as list with one element.
It contains the IP for which the geoip data should be added.

In the following example the IP in :code:`client.ip` will be enriched with geoip data.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: client.ip
    geoip:
      source_fields: [client.ip]
    description: '...'
"""

import warnings
from attrs import define, field, validators


from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import add_and_overwrite, pop_dotted_field_value


class GeoipEnricherRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for GeoipEnricher"""

        target_field: str = field(validator=validators.instance_of(str), default="geoip")
        """Field for the output information. Defaults to :code:`geoip`"""

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
