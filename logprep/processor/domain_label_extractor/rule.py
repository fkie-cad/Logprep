"""
Domain Label Extractor
======================

The domain label extractor requires the additional field :code:`domain_label_extractor`.
The mandatory keys under :code:`domain_label_extractor` are :code:`source_fields` and :code:`target_field`. Former
is used to identify the field (declared as list with one element) which contains the domain.
And the latter is used to define the parent field where theresults should be written to.
Both fields can be dotted subfields. The sub fields of the parent output field of the
result are: :code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`.

In the following example the domain :code:`www.sub.domain.de` will be split into it's subdomain :code:`www.sub`, it's
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

"""
import warnings

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DomainLabelExtractorRule(FieldManagerRule):
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
