"""This module contains a Dropper that deletes specified fields."""

from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.dropper.rule import DropperRule
from logprep.util.processor_stats import ProcessorStats


class DropperError(BaseException):
    """Base class for Dropper related exceptions."""

    def __init__(self, name, message):
        super().__init__(f"Dropper ({name}): {message}")


class Dropper(RuleBasedProcessor):
    """Normalize log events by copying specific values to standardized fields."""

    def __init__(self, name: str, configuration: dict, logger: Logger):
        tree_config = configuration.get("tree_config")
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs,
            specific_rules_dirs=specific_rules_dirs,
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """Add rules from given directory."""
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = DropperRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = DropperRule.create_rules_from_file(rule_path)
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

    def _traverse_dict_and_delete(self, dict_: dict, sub_fields, drop_full: bool):
        sub_field = sub_fields[0] if sub_fields else None
        remaining_sub_fields = sub_fields[1:]

        if not remaining_sub_fields and sub_field in dict_.keys():
            del dict_[sub_field]
        if (
            isinstance(dict_, dict)
            and sub_field in dict_
            and (isinstance(dict_[sub_field], dict) and dict_[sub_field])
        ):
            self._traverse_dict_and_delete(dict_[sub_field], remaining_sub_fields, drop_full)
            if dict_[sub_field] == {} and drop_full:
                del dict_[sub_field]
        elif sub_field in dict_.keys():
            del dict_[sub_field]

    def _drop_field(self, event: dict, dotted_field: str, drop_full: bool):
        sub_fields = dotted_field.split(".")
        self._traverse_dict_and_delete(event, sub_fields, drop_full)

    def _apply_rules(self, event: dict, rule: DropperRule):
        """Drops fields from event Logs."""

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f"{self.describe()} processing matching event")
        for drop_field in rule.fields_to_drop:
            self._try_dropping_field(event, drop_field, rule.drop_full)

    def _try_dropping_field(self, event: dict, dotted_field: str, drop_full: bool):
        if self._field_exists(event, dotted_field):
            self._drop_field(event, dotted_field, drop_full)
