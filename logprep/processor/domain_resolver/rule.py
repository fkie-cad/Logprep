"""
Domain Resolver
===============

The domain resolver requires the additional field :code:`domain_resolver`.
The additional field :code:`domain_resolver.source_fields` must be defined as list with one element.
It contains the field from which an URL should be parsed and then written to :code:`resolved_ip`.
The URL can be located in continuous text insofar the URL is valid.

Optionally, the output field can be configured (overriding the default :code:`resolved_ip`) using the parameter :code:`target_field`.
This can be a dotted subfield.

In the following example the URL from the field :code:`url` will be extracted and written to :code:`resolved_ip`.

..  code-block:: yaml
    :linenos:
    :caption: Example

      filter: url
      domain_resolver:
        source_fields: [url]
      description: '...'
"""
import warnings
from attrs import define, field, fields
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DomainResolverRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for DomainResolver"""

        target_field: list = field(
            validator=fields(FieldManagerRule.Config).target_field.validator,
            default="resolved_ip",
        )
        """The field where to write the processor output to. Defaults to :code:`resovled_ip`"""

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
                    "Use domain_resolver.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("domain_resolver", {}).get("output_field") is not None:
            target_field_value = pop_dotted_field_value(rule, "domain_resolver.output_field")
            add_and_overwrite(rule, "domain_resolver.target_field", target_field_value)
            warnings.warn(
                (
                    "domain_resolver.output_field is deprecated. "
                    "Use domain_resolver.target_field instead"
                ),
                DeprecationWarning,
            )
