"""
This module contains functionality to extract selectively fields from an incoming event. The events will be returned
and written to a specified kafka topic. As the processor is applied to all events it does not need further filtering by
rules.
"""

from multiprocessing import current_process
import os.path
from logging import Logger, DEBUG
from typing import List

from logprep.processor.base.processor import BaseProcessor, RuleBasedProcessor
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class SelectiveExtractorError(BaseException):
    """Base class for Selective Extractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"Selective Extractor ({name}): {message}")


class SelectiveExtractorConfigurationError(SelectiveExtractorError):
    """Generic Selective Extractor configuration error."""


class SelectiveExtractor(RuleBasedProcessor):
    """Processor used to selectively extract fields from log events."""

    _type: str

    _filtered_events: List[tuple] = None

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config, logger)
        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name
        self._filtered_events = []
        generic_rules_dirs = configuration.get("generic_rules")
        specific_rules_dirs = configuration.get("specific_rules")
        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs, specific_rules_dirs=specific_rules_dirs
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = SelectiveExtractorRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = SelectiveExtractorRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"generic rules ({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    def process(self, event: dict) -> tuple:
        super().process(event)
        if self._filtered_events:
            return self._filtered_events
        return None

    def _apply_rules(self, event, rule):
        """
        Generates a filtered event based on the incoming event and the configured
        extraction_fields list in processor configuration or from rule.
        The filtered fields and the target_topic are written to `self._filtered_events` list.

        Parameters
        ----------
        event: dict
            The incoming event that is currently being processed by logprep.

        rule: SelectiveExtractorRule
            The rule to apply

        """
        # filtered events has to be a tuple of (events, target)
        filtered_event = {}

        for field in rule.extracted_field_list:
            field_value = self._get_dotted_field_value(event, field)
            if field_value is not None:
                add_field_to(filtered_event, field, field_value)

        if filtered_event:
            self._filtered_events.append(([filtered_event], rule.target_topic))
