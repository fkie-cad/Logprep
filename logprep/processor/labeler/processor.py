"""This module contains functionality for labeling log events."""

from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List

from time import time

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.exceptions import (
    RuleError,
    InvalidRuleConfigurationError,
    NotARulesDirectoryError,
    KeyDoesnotExistInSchemaError,
    InvalidRuleDefinitionError,
)
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.labeler.exceptions import (
    InvalidSchemaDefinitionError,
    RuleDoesNotConformToLabelingSchemaError,
)
from logprep.processor.labeler.labeling_schema import (
    LabelingSchema,
    InvalidLabelingSchemaFileError,
    LabelingSchemaError,
)
from logprep.processor.labeler.rule import LabelingRule
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


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

        self._specific_tree = RuleTree(config_path=self.tree_config)
        self._generic_tree = RuleTree(config_path=self.tree_config)

        try:
            self._schema = LabelingSchema.create_from_file(configuration.get("schema"))
        except InvalidLabelingSchemaFileError as error:
            raise InvalidSchemaDefinitionError(str(error)) from error

        try:
            self.add_rules_from_directory(
                configuration.get("specific_rules"),
                configuration.get("generic_rules"),
                configuration.get("include_parent_labels", False),
            )
        except (
            InvalidRuleDefinitionError,
            RuleDoesNotConformToLabelingSchemaError,
            NotARulesDirectoryError,
            KeyDoesnotExistInSchemaError,
        ) as error:
            raise InvalidRuleConfigurationError(f"Invalid rule file: {str(error)}") from error

    def describe(self) -> str:
        return f"Labeler ({self._name})"

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self,
        specific_rules_dirs: List[str],
        generic_rules_dirs: List[str],
        include_parent_labels=False,
    ):

        for specific_rules_dir in specific_rules_dirs:
            self.verify_rules_and_add_to(
                self._specific_tree, include_parent_labels, specific_rules_dir
            )

        for generic_rules_dir in generic_rules_dirs:
            self.verify_rules_and_add_to(
                self._generic_tree, include_parent_labels, generic_rules_dir
            )

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
    
    def verify_rules_and_add_to(self, tree, include_parent_labels, rules_dir):
        """
        Creates LabelingRules, verifies if they conform with the given schema and adds them to
        the given rule_tree.

        Parameters
        ----------
        tree : RuleTree
            The rule tree to which the new rules should be added to.
        include_parent_labels : bool
            A flag that decides whether labels from the parent schema should be added to the rule
            or not.
        rules_dir : str
            The path to the directory with the rule configurations that should be added to the
            rule tree
        """
        rule_paths = self._list_json_files_in_directory(rules_dir)
        for rule_path in rule_paths:
            rules = LabelingRule.create_rules_from_file(rule_path)
            for rule in rules:
                if include_parent_labels:
                    try:
                        rule.add_parent_labels_from_schema(self._schema)
                    except LabelingSchemaError as error:
                        raise InvalidRuleConfigurationError(
                            f"Rule does not conform to labeling schema: {rule_path}"
                        ) from error

                try:
                    rule.conforms_to_schema(self._schema)
                except RuleError as error:
                    raise InvalidRuleConfigurationError(
                        f"Rule does not conform to labeling schema: {rule_path}"
                    ) from error

                tree.add_rule(rule, self._logger)


    @TimeMeasurement.measure_time("labeler")
    def process(self, event: dict):
        """Process the current event"""
        self._add_labels(event)
        self._convert_label_categories_to_sorted_list(event)
        self.ps.increment_processed_count()

    def _add_labels(self, event: dict):
        for rule in self._generic_tree.get_matching_rules(event):
            begin = time()
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug(f"{self.describe()} processing matching event")
            rule.add_labels(event)

            processing_time = float(f"{time() - begin:.10f}")
            idx = self._generic_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._specific_tree.get_matching_rules(event):
            begin = time()
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug(f"{self.describe()} processing matching event")
            rule.add_labels(event)

            processing_time = float(f"{time() - begin:.10f}")
            idx = self._specific_tree.get_rule_id(rule)

            self.ps.update_per_rule(idx, processing_time)

    @staticmethod
    def _convert_label_categories_to_sorted_list(event: dict):
        if "label" in event:
            for category in event["label"]:
                event["label"][category] = sorted(list(event["label"][category]))
