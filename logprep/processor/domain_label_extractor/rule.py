"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The domain label extractor requires the additional field :code:`domain_label_extractor`.
The mandatory keys under :code:`domain_label_extractor` are :code:`source_fields`
and :code:`target_field`. Former is used to identify the field
(declared as list with one element) which contains the domain.
And the latter is used to define the parent field where theresults should be written to.
Both fields can be dotted subfields. The sub fields of the parent output field of the
result are: :code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`.

In the following example the domain :code:`www.sub.domain.de`
will be split into it's subdomain :code:`www.sub`, it's
registered domain :code:`domain` and lastly it's TLD :code:`de`:

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to extract the labels / parts of a domain.

    filter: 'url'
    domain_label_extractor:
      source_fields: ['url.domain']
      target_field: 'url'
    description: '...'

The example rule applied to the input event

..  code-block:: json
    :caption: Input Event

    {
        "url": {
            "domain": "www.sub.domain.de"
        }
    }

will result in the following output

..  code-block:: json
    :caption: Output Event

    {
        "url": {
            "domain": "www.sub.domain.de",
            "registered_domain": "domain.de",
            "top_level_domain": "de",
            "subdomain": "www.sub"
        }
    }

.. autoclass:: logprep.processor.domain_label_extractor.rule.DomainLabelExtractorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attr import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule


class DomainLabelExtractorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for DomainLabelExtractorRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
        )
        """The fields from where to get the values which should be processed."""
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
