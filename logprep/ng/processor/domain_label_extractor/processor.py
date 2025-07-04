"""
DomainLabelExtractor
====================

The `domain_label_extractor` is a processor that splits a domain into it's corresponding labels
like :code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`. If instead an IP
is given in the target field an informational tag is added to the configured tags field. If
neither a domain nor an ip address can be recognized an invalid error tag will be added to the
tag field in the event. The added tags contain each the target field name that was checked by the
configured rule, such that it is possible to distinguish between different domain fields in one
event. For example for the target field :code:`url.domain` following tags could be added:
:code:`invalid_domain_in_url_domain` and :code:`ip_in_url_domain`

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - domainlabelextractorname:
        type: domain_label_extractor
        rules:
            - tests/testdata/rules/rules
        tagging_field_name: resolved

.. autoclass:: logprep.processor.domain_label_extractor.processor.DomainLabelExtractor.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.domain_label_extractor.rule
"""

import ipaddress
import logging
from urllib.parse import urlsplit

from attr import define, field, validators

from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import add_and_overwrite, add_fields_to, get_dotted_field_value
from logprep.util.url.url import Domain

logger = logging.getLogger("DomainLabelExtractor")


class DomainLabelExtractor(FieldManager):
    """Splits a domain into it's parts/labels."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """DomainLabelExtractor config"""

        tagging_field_name: str = field(
            default="tags", validator=validators.optional(validators.instance_of(str))
        )
        """Optional configuration field that defines into which field in the event the
        informational tags should be written to. If this field is not present it defaults
        to :code:`tags`."""

    rule_class = DomainLabelExtractorRule

    def _apply_rules(self, event, rule: DomainLabelExtractorRule):
        """
        Apply matching rule to given log event. Such that a given domain,
        configured via rule, is split into it's labels and parts. The resulting
        subfields will be saved in the configured output field.
        In case no valid tld is recognized this method checks if the target
        field has an ipv4 or ipv6 address, if so nothing will be done.
        If also no ip-address is recognized the tag 'unrecognized_domain' is
        added to the event.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied domain label extractor rule.
        """
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, rule.source_fields, source_field_values)
        domain = source_field_values[0]
        if domain is None:
            return
        tagging_field = get_dotted_field_value(event, self._config.tagging_field_name)
        if tagging_field is None:
            tagging_field = []

        if self._is_valid_ip(domain):
            tagging_field.append(f"ip_in_{rule.source_fields[0].replace('.', '_')}")
            add_and_overwrite(
                event, fields={self._config.tagging_field_name: tagging_field}, rule=rule
            )
            return

        url = urlsplit(domain)
        domain = url.hostname
        if url.scheme == "":
            domain = url.path
        labels = Domain(domain)
        if labels.suffix != "":
            fields = {
                f"{rule.target_field}.registered_domain": f"{labels.domain}.{labels.suffix}",
                f"{rule.target_field}.top_level_domain": labels.suffix,
                f"{rule.target_field}.subdomain": labels.subdomain,
            }
            add_fields_to(event, fields, rule, overwrite_target=rule.overwrite_target)
        else:
            tagging_field.append(f"invalid_domain_in_{rule.source_fields[0].replace('.', '_')}")
            add_and_overwrite(
                event, fields={self._config.tagging_field_name: tagging_field}, rule=rule
            )

    @staticmethod
    def _is_valid_ip(domain):
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            return False
