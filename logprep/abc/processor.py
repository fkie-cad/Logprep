""" abstract module for processors"""
import copy
from abc import abstractmethod
from logging import DEBUG, Logger
from multiprocessing import current_process
from typing import List, Optional

from attr import define, field
from logprep.abc import Component

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric import Metric, calculate_new_average
from logprep.processor.base.rule import Rule
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.processor_strategy import SpecificGenericProcessStrategy
from logprep.util.json_handling import list_json_files_in_directory
from logprep.util.time_measurement import TimeMeasurement
from logprep.util.validators import file_validator, list_of_dirs_validator
from logprep.util.helper import pop_dotted_field_value, get_dotted_field_value, add_and_overwrite


class Processor(Component):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config(Component.Config):
        """Common Configurations"""

        specific_rules: List[str] = field(validator=list_of_dirs_validator)
        """List of directory paths with generic rule files that can match multiple event types"""
        generic_rules: List[str] = field(validator=list_of_dirs_validator)
        """List of directory paths with generic rule files that can match multiple event types"""
        tree_config: Optional[str] = field(default=None, validator=[file_validator])
        """ Path to a JSON file with a valid rule tree configuration. """

    @define(kw_only=True)
    class ProcessorMetrics(Metric):
        """Tracks statistics about this processor"""

        _prefix: str = "logprep_processor_"

        number_of_processed_events: int = 0
        """Number of events that were processed by the processor"""
        mean_processing_time_per_event: float = 0.0
        """Mean processing time for one event"""
        _mean_processing_time_sample_counter: int = 0
        number_of_warnings: int = 0
        """Number of warnings that occurred while processing events"""
        number_of_errors: int = 0
        """Number of errors that occurred while processing events"""
        generic_rule_tree: RuleTree.RuleTreeMetrics
        """Tracker of the generic rule tree metrics"""
        specific_rule_tree: RuleTree.RuleTreeMetrics
        """Tracker of the specific rule tree metrics"""

        def update_mean_processing_time_per_event(self, new_sample):
            """Updates the mean processing time per event"""
            new_avg, new_sample_counter = calculate_new_average(
                self.mean_processing_time_per_event,
                new_sample,
                self._mean_processing_time_sample_counter,
            )
            self.mean_processing_time_per_event = new_avg
            self._mean_processing_time_sample_counter = new_sample_counter

    __slots__ = [
        "rule_class",
        "has_custom_tests",
        "metrics",
        "metric_labels",
        "_event",
        "_specific_tree",
        "_generic_tree",
    ]

    rule_class: Rule
    has_custom_tests: bool
    metrics: ProcessorMetrics
    metric_labels: dict
    _event: dict
    _specific_tree: RuleTree
    _generic_tree: RuleTree

    _strategy = SpecificGenericProcessStrategy()

    def __init__(self, name: str, configuration: "Processor.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self.metric_labels, specific_tree_labels, generic_tree_labels = self._create_metric_labels()
        self._specific_tree = RuleTree(
            config_path=self._config.tree_config, metric_labels=specific_tree_labels
        )
        self._generic_tree = RuleTree(
            config_path=self._config.tree_config, metric_labels=generic_tree_labels
        )
        self.add_rules_from_directory(
            generic_rules_dirs=self._config.generic_rules,
            specific_rules_dirs=self._config.specific_rules,
        )
        self.metrics = self.ProcessorMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self.has_custom_tests = False

    def _create_metric_labels(self):
        """Reads out the metrics from the configuration and sets up labels for the rule trees"""
        metric_labels = self._config.metric_labels
        metric_labels.update({"processor": self.name})
        specif_tree_labels = copy.deepcopy(metric_labels)
        specif_tree_labels.update({"rule_tree": "specific"})
        generic_tree_labels = copy.deepcopy(metric_labels)
        generic_tree_labels.update({"rule_tree": "generic"})
        return metric_labels, specif_tree_labels, generic_tree_labels

    @property
    def _specific_rules(self):
        """Returns all specific rules

        Returns
        -------
        specific_rules: list[Rule]
        """
        return self._specific_tree.rules

    @property
    def _generic_rules(self):
        """Returns all generic rules

        Returns
        -------
        generic_rules: list[Rule]
        """
        return self._generic_tree.rules

    @property
    def _rules(self):
        """Returns all rules

        Returns
        -------
        rules: list[Rule]
        """
        return [*self._generic_rules, *self._specific_rules]

    @TimeMeasurement.measure_time()
    def process(self, event: dict):
        """Process a log event by calling the implemented `process` method of the
        strategy object set in  `_strategy` attribute.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"{self.describe()} processing event {event}")
        self._strategy.process(
            event,
            generic_tree=self._generic_tree,
            specific_tree=self._specific_tree,
            callback=self._apply_rules_wrapper,
            processor_metrics=self.metrics,
        )

    def _apply_rules_wrapper(self, event, rule):
        self._apply_rules(event, rule)
        if not hasattr(rule, "delete_source_fields"):
            return
        if rule.delete_source_fields:
            for dotted_field in rule.source_fields:
                pop_dotted_field_value(event, dotted_field)

    @abstractmethod
    def _apply_rules(self, event, rule):
        ...  # pragma: no cover

    def test_rules(self) -> dict:
        """Perform custom rule tests.

        Returns a dict with a list of test results as tuples containing a result and an expected
        result for each rule, i.e. {'RULE REPR': [('Result string', 'Expected string')]}
        Optional: Can be used in addition to regular rule tests.

        """

    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """method to add rules from directory"""
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = self.rule_class.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = self.rule_class.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            number_specific_rules = self._specific_tree.metrics.number_of_rules
            self._logger.debug(
                f"{self.describe()} loaded {number_specific_rules} "
                f"specific rules ({current_process().name})"
            )
            number_generic_rules = self._generic_tree.metrics.number_of_rules
            self._logger.debug(
                f"{self.describe()} loaded {number_generic_rules} generic rules "
                f"generic rules ({current_process().name})"
            )

    @staticmethod
    def _field_exists(event: dict, dotted_field: str) -> bool:
        fields = dotted_field.split(".")
        dict_ = event
        for field_ in fields:
            if field_ in dict_ and isinstance(dict_, dict):
                dict_ = dict_[field_]
            else:
                return False
        return True

    @staticmethod
    def _handle_warning_error(event, rule, error):
        tags = get_dotted_field_value(event, "tags")
        if tags is None:
            add_and_overwrite(event, "tags", sorted(list({*rule.failure_tags})))
        else:
            add_and_overwrite(event, "tags", sorted(list({*tags, *rule.failure_tags})))
        raise ProcessingWarning(str(error)) from error
