""" This module contains functionality to split a domain into it's parts/labels. """
import socket
from logging import Logger, DEBUG
from multiprocessing import current_process
from time import time
from typing import List

from tldextract import TLDExtract

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    InvalidRuleFileError,
)
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats, StatsClassesController
from logprep.util.time_measurement import TimeMeasurement

StatsClassesController.ENABLED = True


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

    def __init__(
        self,
        name: str,
        configuration: dict,
        tld_lists: list,
        tagging_field_name: str,
        logger: Logger,
    ):
        """
        Initializes the DomainLabelExtractor processor.

        Parameters
        ----------
        name : str
            Name of the DomainLabelExtractor processor (as referred to in the pipeline).
        tree_config : str
            Path to the configuration file which can prioritize fields and add conditional rules.
        tld_lists : list
            Optional list of paths to tld-suffix lists. If 'none' a default list will be retrieved online.
        logger : Logger
            Standard logger.
        """

        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config=tree_config, logger=logger)
        self.ps = ProcessorStats()
        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)
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

    def _load_rules_from_file(self, path: str):
        """
        Collect rule(s) from a given file.

        Parameters
        ----------
        path : str
            Path to the file containing a DomainLabelExtractor rule.

        """

        try:
            return DomainLabelExtractorRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path, str(error)) from error

    def describe(self) -> str:
        """Return name of given processor instance."""
        return f"DomainLabelExtractor ({self._name})"

    @TimeMeasurement.measure_time("domain_label_extractor")
    def process(self, event: dict):
        """
        Process log message.

        Parameters
        ----------
        event : dict
            Current event log message to be processed.
        """
        self._event = event

        for rule in self._specific_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(self._event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._specific_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._generic_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        self.ps.increment_processed_count()

    def _apply_rules(self, event, rule: DomainLabelExtractorRule):
        """
        Apply matching rule to given log event. Such that a given domain, configured via rule, is split into it's
        labels and parts. The resulting subfields will be saved in the configured output field.
        In case no valid tld is recognized this method checks if the target field has an ipv4 or ipv6 address, if so
        nothing will be done. If also no ip-address is recognized the tag 'unrecognized_domain' is added to the event.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied domain label extractor rule.
        """

        if self._field_exists(event, rule.target_field):
            domain = self._get_dotted_field_value(event, rule.target_field)

            labels = self._tld_extractor(domain)

            if labels.suffix != "":
                labels_dict = {
                    "registered_domain": labels.domain + "." + labels.suffix,
                    "top_level_domain": labels.suffix,
                    "subdomain": labels.subdomain,
                }

                # add results to event
                for label in labels_dict.keys():
                    output_field = f"{rule.output_field}.{label}"
                    adding_was_successful = add_field_to(event, output_field, labels_dict[label])

                    if not adding_was_successful:
                        raise DuplicationError(self._name, [output_field])
            else:
                try:
                    # check if ip address is ipv4
                    socket.inet_aton(labels.domain)
                    event[self._tagging_field_name] = event.get(self._tagging_field_name, []) + [
                        f"ip_in_{rule.target_field.replace('.', '_')}"
                    ]
                except OSError:
                    try:
                        # check if ip address is ipv6
                        socket.inet_pton(socket.AF_INET6, labels.domain)
                        event[self._tagging_field_name] = event.get(
                            self._tagging_field_name, []
                        ) + [f"ip_in_{rule.target_field.replace('.', '_')}"]
                    except OSError:
                        # if it's neither ipv4 nor ipv6 then add error tag
                        event[self._tagging_field_name] = event.get(
                            self._tagging_field_name, []
                        ) + [f"invalid_domain_in_{rule.target_field.replace('.', '_')}"]
