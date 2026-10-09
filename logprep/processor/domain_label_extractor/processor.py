"""
|PROCESSOR_NAME|
================

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
import typing
from urllib.parse import urlsplit

from attrs import define, field, validators

from logprep.processor.base.exceptions import ProcessingCriticalError
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import (
    MISSING,
    add_and_overwrite,
    add_fields_to,
    get_dotted_field_list,
    get_dotted_field_value_with_missing,
    join_dotted_fields,
)
from logprep.util.url.url import Domain

logger = logging.getLogger("DomainLabelExtractor")


class DomainLabelExtractor(FieldManager):
    """Splits a domain into it's parts/labels."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config for |PROCESSOR|"""

        tagging_field_name: str = field(default="tags", validator=validators.instance_of(str))
        """Optional configuration field that defines into which field in the event the
        informational tags should be written to. If this field is not present it defaults
        to :code:`tags`."""

    rule_class = DomainLabelExtractorRule

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(DomainLabelExtractor.Config, self._config)

    def _apply_rules(self, event, rule):
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
        assert len(rule.source_fields) == 1
        source_field = rule.source_fields[0]

        def _fail(fail_tag: str) -> None:
            tagging_field = get_dotted_field_value_with_missing(
                event, self.config.tagging_field_name
            )
            print(self.config.tagging_field_name)
            print(tagging_field)
            if tagging_field is MISSING:
                tagging_field = []

            if isinstance(tagging_field, str):
                tagging_field = [tagging_field]
            if not isinstance(tagging_field, list):
                raise ProcessingCriticalError(
                    f"Field {self.config.tagging_field_name!r} specified for "
                    f" tagging already has a conflicting value of type {type(tagging_field).__name__}"
                    " expected list.",
                    rule=rule,
                )
            tagging_field.append(fail_tag)
            add_and_overwrite(
                event, fields={self.config.tagging_field_name: tagging_field}, rule=rule
            )

        def _fail_on_source(reason: str) -> None:
            _fail(f"{reason}_in_{'_'.join(get_dotted_field_list(source_field))}")

        domain = get_dotted_field_value_with_missing(event, source_field)

        if domain is MISSING:
            _fail(f"_{rule.rule_type}_missing_field_warning")
            return

        def _set_result(registered: str, tld: str, sub: str) -> None:
            fields = {
                join_dotted_fields((rule.target_field, "registered_domain")): registered,
                join_dotted_fields((rule.target_field, "top_level_domain")): tld,
                join_dotted_fields((rule.target_field, "subdomain")): sub,
            }
            add_fields_to(event, fields, rule, overwrite_target=rule.overwrite_target)

        if not isinstance(domain, str):
            _fail_on_source("invalid_type")
            return

        if self._is_valid_ip(domain):
            _fail_on_source("ip")
            return

        try:
            url = urlsplit(domain)
        except:
            _fail_on_source("invalid_domain")
            return

        hostname = url.hostname if url.scheme != "" else url.path
        if hostname is None or len(hostname.strip()) == 0:
            _set_result(registered="", tld="", sub="")
            return

        labels = Domain(hostname)
        if labels.suffix == "":
            _set_result(registered="", tld="", sub="")
            return

        _set_result(
            registered=f"{labels.domain}.{labels.suffix}",
            tld=labels.suffix,
            sub=labels.subdomain,
        )

    @staticmethod
    def _is_valid_ip(domain):
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            return False
