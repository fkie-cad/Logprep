"""This module contains functionality for adding fields using regex lists."""
from time import time
from typing import List
from logging import Logger, DEBUG

from os import walk
from os.path import isdir, realpath, join

from multiprocessing import current_process
from logprep.framework.rule_tree.rule_tree import RuleTree

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.processor.base.exceptions import (
    NotARulesDirectoryError,
    InvalidRuleDefinitionError,
    InvalidRuleFileError,
)

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class GenericAdderError(BaseException):
    """Base class for GenericAdder related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericAdder ({name}): {message}")


class DuplicationError(GenericAdderError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and " "were not overwritten by the GenericAdder: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GenericAdder(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, configuration: dict, logger: Logger):
        tree_config = configuration.get("tree_config")
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()
        self._generic_tree = RuleTree(tree_config)
        self._specific_tree = RuleTree(tree_config)
        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs,
            specific_rules_dirs=specific_rules_dirs,
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = GenericAdderRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = GenericAdderRule.create_rules_from_file(rule_path)
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
        try:
            return GenericAdderRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path, str(error)) from error

    def describe(self) -> str:
        return f"GenericAdder ({self._name})"

    @TimeMeasurement.measure_time("generic_adder")
    def process(self, event: dict):
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
        conflicting_fields = list()

        for dotted_field, value in rule.add.items():
            keys = dotted_field.split(".")
            dict_ = event
            for idx, key in enumerate(keys):
                if key not in dict_:
                    if idx == len(keys) - 1:
                        dict_[key] = value
                        break
                    dict_[key] = dict()

                if isinstance(dict_[key], dict):
                    dict_ = dict_[key]
                else:
                    conflicting_fields.append(keys[idx])

        if conflicting_fields:
            raise DuplicationError(self._name, conflicting_fields)
