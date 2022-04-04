"""
This module contains functionality for checking if values exist or not exist in file lists. This processor implements
black- and whitelisting capabilities.
"""
from logging import Logger, DEBUG
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.framework import rule_tree
from multiprocessing import current_process
from os import walk
from os.path import isdir, realpath, join
from time import time
from typing import List, Optional

from logprep.processor.base.exceptions import (
    NotARulesDirectoryError,
    InvalidRuleDefinitionError,
    InvalidRuleFileError,
)
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class ListComparisonError(BaseException):
    """Base class for ListComparison related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"ListComparison ({name}): {message}")


class DuplicationError(ListComparisonError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields could not be written, because "
            "one or more subfields existed and could not be extended: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class ListComparison(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(
        self,
        name: str,
        tree_config: str,
        list_search_base_path: Optional[str],
        logger: Logger,
    ):
        """
        Initializes the list_comparison processor.

        Parameters
        ----------
        name : str
            Name of the list_comparison processor (as referred to in the pipeline).
        tree_config : str
            Path to the configuration file which can prioritize fields and add conditional rules.
        logger : Logger
            Standard logger.
        """
        super().__init__(name, tree_config, logger)
        self._list_search_base_dir = list_search_base_path
        self.ps = ProcessorStats()
        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = ListComparisonRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = ListComparisonRule.create_rules_from_file(rule_path)
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

    def _load_rules_from_file(self, list_comparison_path: str):
        """
        Collect rule(s) from a given file.

        Parameters
        ----------
        path : str
            Path to the file containing a list_comparison rule.

        """
        try:
            return ListComparisonRule.create_rules_from_file(list_comparison_path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, list_comparison_path, str(error)) from error

    def describe(self) -> str:
        """Return name of given processor instance."""
        return f"ListComparison ({self._name})"

    @TimeMeasurement.measure_time("list_comparison")
    def process(self, event: dict):
        """
        Process log message.

        Parameters
        ----------
        event : dict
            Current event log message to be processed.

        """

        self._event = event

        for rule in self._generic_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._generic_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._specific_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._specific_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        self.ps.increment_processed_count()

    def _apply_rules(self, event, rule):
        """
        Apply matching rule to given log event.
        In the process of doing so, add the result of comparing
        the log with a given list to the specified subfield. This subfield will contain
        a list of list comparison results that might be based on multiple rules.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied list comparison rule.

        """

        comparison_result, comparison_key = self._list_comparison(rule, event)

        if comparison_result is not None:
            output_field = f"{ rule.list_comparison_output_field }.{ comparison_key }"
            field_possible = add_field_to(event, output_field, comparison_result, True)
            if not field_possible:
                raise DuplicationError(self._name, [output_field])

    def _list_comparison(self, rule: ListComparisonRule, event: dict):
        """
        Check if field value violates block or allow list.
        Returns the result of the comparison (res_key), as well as a dictionary containing the result (key)
        and a list of filenames pertaining to said result (value).
        """

        # get value that should be checked in the lists
        field_value = self._get_dotted_field_value(event, rule.check_field)

        # iterate over lists and check if element is in any
        list_matches = []
        for compare_list in rule.compare_sets.keys():
            if field_value in rule.compare_sets[compare_list]:
                list_matches.append(compare_list)

        # if matching list was found return it, otherwise return all list names
        if len(list_matches) > 0:
            return list_matches, "in_list"
        elif len(list_matches) == 0:
            return list(rule.compare_sets.keys()), "not_in_list"
