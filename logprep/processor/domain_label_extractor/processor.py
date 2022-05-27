""" This module contains functionality to split a domain into it's parts/labels. """
import ipaddress
from logging import Logger
from typing import List
from attr import define, field, validators

from tldextract import TLDExtract

from logprep.abc import Processor
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.util.helper import add_field_to


class DomainLabelExtractorError(BaseException):
    """Base class for DomainLabelExtractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DomainLabelExtractor ({name}): {message}")


class DuplicationError(DomainLabelExtractorError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the DomainLabelExtractor: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class DomainLabelExtractor(Processor):
    """Splits a domain into it's parts/labels."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """domain_label_extractor config"""

        tagging_field_name: str = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )

        tld_lists: list = field(factory=list, validator=validators.instance_of(list))

    __slots__ = ["_tld_extractor", "_tagging_field_name"]

    _tld_extractor: TLDExtract

    _tagging_field_name: str

    rule_class = DomainLabelExtractorRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        """
        Initializes the DomainLabelExtractor processor.

        Parameters
        ----------
        name : str
            Name of the DomainLabelExtractor processor (as referred to in the pipeline).
        configuration : dict
            Configuration of the processor
        logger : Logger
            Standard logger.
        """

        tld_lists = configuration.get("tld_lists")
        super().__init__(name=name, configuration=configuration, logger=logger)

        if tld_lists is not None:
            self._tld_extractor = TLDExtract(suffix_list_urls=tld_lists)
        else:
            self._tld_extractor = TLDExtract()

        self._tagging_field_name = configuration.get("tagging_field_name", "tags")

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
        if not self._field_exists:
            return
        domain = self._get_dotted_field_value(event, rule.target_field)
        tagging_field = event.get(self._tagging_field_name, [])

        if self._is_valid_ip(domain):
            tagging_field.append(f"ip_in_{rule.target_field.replace('.', '_')}")
            event[self._tagging_field_name] = tagging_field
            return

        labels = self._tld_extractor(domain)
        if labels.suffix != "":
            labels_dict = {
                "registered_domain": labels.domain + "." + labels.suffix,
                "top_level_domain": labels.suffix,
                "subdomain": labels.subdomain,
            }
            for label, _ in labels_dict.items():
                output_field = f"{rule.output_field}.{label}"
                adding_was_successful = add_field_to(event, output_field, labels_dict[label])

                if not adding_was_successful:
                    raise DuplicationError(self.name, [output_field])
        else:
            tagging_field.append(f"invalid_domain_in_{rule.target_field.replace('.', '_')}")
            event[self._tagging_field_name] = tagging_field

    @staticmethod
    def _is_valid_ip(domain):
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            return False
