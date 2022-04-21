"""This module contains functionality for labeling log events."""

from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List


from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.labeler.labeling_schema import (
    LabelingSchema,
)
from logprep.processor.labeler.rule import LabelingRule
from logprep.util.processor_stats import ProcessorStats


class Labeler(RuleBasedProcessor):
    """Processor used to label log events."""

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        self.tree_config = configuration.get("tree_config")
        super().__init__(name, self.tree_config, logger)

        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name

        self._include_parent_labels = configuration.get("include_parent_labels", False)

        self._specific_tree = RuleTree(config_path=self.tree_config)
        self._generic_tree = RuleTree(config_path=self.tree_config)

        self._schema = LabelingSchema.create_from_file(configuration.get("schema"))

        self.add_rules_from_directory(
            configuration.get("specific_rules"),
            configuration.get("generic_rules"),
        )

    def describe(self) -> str:
        return f"Labeler ({self._name})"

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self,
        specific_rules_dirs: List[str],
        generic_rules_dirs: List[str],
    ):

        for specific_rules_dir in specific_rules_dirs:
            self.verify_rules_and_add_to(self._specific_tree, specific_rules_dir)

        for generic_rules_dir in generic_rules_dirs:
            self.verify_rules_and_add_to(self._generic_tree, generic_rules_dir)

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

    def verify_rules_and_add_to(self, tree, rules_dir):
        """
        Creates LabelingRules, verifies if they conform with the given schema and adds them to
        the given rule_tree.

        Parameters
        ----------
        tree : RuleTree
            The rule tree to which the new rules should be added to.
        rules_dir : str
            The path to the directory with the rule configurations that should be added to the
            rule tree
        """
        rule_paths = self._list_json_files_in_directory(rules_dir)
        for rule_path in rule_paths:
            rules = LabelingRule.create_rules_from_file(rule_path)
            for rule in rules:
                if self._include_parent_labels:
                    rule.add_parent_labels_from_schema(self._schema)

                rule.conforms_to_schema(self._schema)

                tree.add_rule(rule, self._logger)

    def _apply_rules(self, event, rule):
        """Applies the rule to the current event"""
        self._add_label_fields(event, rule)
        self._add_label_values(event, rule)
        self._convert_label_categories_to_sorted_list(event)

    @staticmethod
    def _add_label_fields(event: dict, rule: LabelingRule):
        """Prepares the event by adding empty label fields"""
        if "label" not in event:
            event["label"] = {}

        for key in rule.label:
            if key not in event["label"]:
                event["label"][key] = set()

    @staticmethod
    def _add_label_values(event: dict, rule: LabelingRule):
        """Adds the labels from the rule to the event"""
        for key in rule.label:
            if not isinstance(event["label"][key], set):
                event["label"][key] = set(event["label"][key])

            event["label"][key].update(rule.label[key])

    @staticmethod
    def _convert_label_categories_to_sorted_list(event: dict):
        if "label" in event:
            for category in event["label"]:
                event["label"][category] = sorted(list(event["label"][category]))
