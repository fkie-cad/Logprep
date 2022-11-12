"""
DomainLabelExtractor
--------------------

The `domain_label_extractor` is a processor that splits a domain into it's corresponding labels
like :code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`. If instead an IP
is given in the target field an informational tag is added to the configured tags field. If
neither a domain nor an ip address can be recognized an invalid error tag will be be added to the
tag field in the event. The added tags contain each the target field name that was checked by the
configured rule, such that it is possible to distinguish between different domain fields in one
event. For example for the target field :code:`url.domain` following tags could be added:
:code:`invalid_domain_in_url_domain` and :code:`ip_in_url_domain`


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - domainlabelextractorname:
        type: domain_label_extractor
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        tld_lists: /path/to/list/file
        tagging_field_name: resolved
"""
import sys
import ipaddress

from typing import Optional
from attr import define, field, validators

from tldextract import TLDExtract


from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.util.validators import list_of_urls_validator
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.util.helper import add_field_to, get_dotted_field_value

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class DomainLabelExtractor(Processor):
    """Splits a domain into it's parts/labels."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """DomainLabelExtractor config"""

        tagging_field_name: str = field(
            default="tags", validator=validators.optional(validators.instance_of(str))
        )
        """Optional configuration field that defines into which field in the event the
        informational tags should be written to. If this field is not present it defaults
        to :code:`tags`."""
        tld_lists: Optional[list] = field(default=None, validator=[list_of_urls_validator])
        """Optional list of path to files with top-level domain lists
        (like https://publicsuffix.org/list/public_suffix_list.dat). If no path is given,
        a default list will be retrieved online and cached in a local directory. For local
        files the path has to be given with :code:`file:///path/to/file.dat`."""

    rule_class = DomainLabelExtractorRule

    __slots__ = ["detection_results", "_pre_detector_topic", "_ids"]

    @cached_property
    def _tld_extractor(self):
        if self._config.tld_lists is not None:
            _tld_extractor = TLDExtract(suffix_list_urls=self._config.tld_lists)
        else:
            _tld_extractor = TLDExtract()
        return _tld_extractor

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
        domain = get_dotted_field_value(event, rule.source_fields[0])
        if domain is None:
            return
        tagging_field = event.get(self._config.tagging_field_name, [])

        if self._is_valid_ip(domain):
            tagging_field.append(f"ip_in_{rule.source_fields[0].replace('.', '_')}")
            event[self._config.tagging_field_name] = tagging_field
            return

        labels = self._tld_extractor(domain)
        if labels.suffix != "":
            labels_dict = {
                "registered_domain": labels.domain + "." + labels.suffix,
                "top_level_domain": labels.suffix,
                "subdomain": labels.subdomain,
            }
            for label, value in labels_dict.items():
                output_field = f"{rule.target_field}.{label}"
                add_successful = add_field_to(
                    event, output_field, value, overwrite_output_field=rule.overwrite_target
                )

                if not add_successful:
                    raise DuplicationError(self.name, [output_field])
        else:
            tagging_field.append(f"invalid_domain_in_{rule.source_fields[0].replace('.', '_')}")
            event[self._config.tagging_field_name] = tagging_field

    @staticmethod
    def _is_valid_ip(domain):
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            return False
