""" This module contains functionality to split a domain into it's parts/labels. """
import ipaddress
from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List

from tldextract import TLDExtract

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats


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


class DomainLabelExtractor(RuleBasedProcessor):
    """Splits a domain into it's parts/labels."""

    def __init__(self, name: str, configuration: dict, logger: Logger):
        """
        Initializes the DomainLabelExtractor processor.

        Parameters
        ----------
        name : str
            Name of the DomainLabelExtractor processor (as referred to in the pipeline).
        configuraiton : dict
            Configuration of the processor
        logger : Logger
            Standard logger.
        """

        tree_config = configuration.get("tree_config")
        tld_lists = configuration.get("tld_lists")
        tagging_field_name = configuration.get("tagging_field_name", "tags")
        super().__init__(name, tree_config=tree_config, logger=logger)
        self.ps = ProcessorStats()
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs,
            specific_rules_dirs=specific_rules_dirs,
        )

        if tld_lists is not None:
            self._tld_extractor = TLDExtract(suffix_list_urls=tld_lists)
        else:
            self._tld_extractor = TLDExtract()

        self._tagging_field_name = tagging_field_name

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """
        Collect rules from given directory.

        Parameters
        ----------
        specific_rules_dirs : List[str]
            Path to the directory containing specific DomainLabelExtractor rules.
        generic_rules_dirs : List[str]
            Path to the directory containing specific DomainLabelExtractor rules.

        """
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = DomainLabelExtractorRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = DomainLabelExtractorRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"({current_process().name})"
            )

        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

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
                    raise DuplicationError(self._name, [output_field])
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
