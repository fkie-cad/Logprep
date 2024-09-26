"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

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

.. autoclass:: logprep.processor.domain_resolver.rule.DomainResolverRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attrs import define, field, fields

from logprep.processor.field_manager.rule import FieldManagerRule


class DomainResolverRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for DomainResolver"""

        target_field: str = field(
            validator=fields(FieldManagerRule.Config).target_field.validator,
            default="resolved_ip",
        )
        """The field where to write the processor output to. Defaults to :code:`resovled_ip`"""
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
