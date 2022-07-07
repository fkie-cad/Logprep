""" abstract module for processors"""
import copy
import os
import sys
from abc import ABC, abstractmethod
from logging import DEBUG, Logger
from multiprocessing import current_process
from typing import List, Optional, Union

from attr import define, field, validators

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric import Metric, calculate_new_average
from logprep.processor.base.rule import Rule
from logprep.processor.processor_strategy import SpecificGenericProcessStrategy
from logprep.util.helper import camel_to_snake
from logprep.util.json_handling import list_json_files_in_directory
from logprep.util.time_measurement import TimeMeasurement
from logprep.util.validators import file_validator, list_of_dirs_validator


class Processor(ABC):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config:
        """Common Configurations"""

        type: str = field(validator=validators.instance_of(str))
        """ The type value defines the processor type that is being configured. """
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
        "name",
        "rule_class",
        "has_custom_tests",
        "metrics",
        "metric_labels",
        "_logger",
        "_event",
        "_specific_tree",
        "_generic_tree",
        "_config",
    ]

    if not sys.version_info.minor < 7:
        __slots__.append("__dict__")

    name: str
    rule_class: Rule
    has_custom_tests: bool
    metrics: ProcessorMetrics
    metric_labels: dict
    _config: Config
    _logger: Logger
    _event: dict
    _specific_tree: RuleTree
    _generic_tree: RuleTree

    _strategy = SpecificGenericProcessStrategy()

    def __init__(self, name: str, configuration: "Processor.Config", logger: Logger):
        self._logger = logger
        self._config = configuration
        self.name = name
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

    def __repr__(self):
        return camel_to_snake(self.__class__.__name__)

    def setup(self):
        """Set the processor up.

        Optional: Called before processing starts.

        """

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

    def describe(self) -> str:
        """Provide a brief name-like description of the processor.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> Labeler(name)

        """
        return f"{self.__class__.__name__} ({self.name})"

    @TimeMeasurement.measure_time()
    def process(self, event: dict):
        """Process a log event by calling the implemented `process` method of the
        strategy object set in  `_strategy` attribute.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug("%s process event %s", self, event)
        self._strategy.process(
            event,
            generic_tree=self._generic_tree,
            specific_tree=self._specific_tree,
            callback=self._apply_rules,
            processor_metrics=self.metrics,
        )

    @abstractmethod
    def _apply_rules(self, event, rule):
        ...  # pragma: no cover

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """

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
        if self._logger.isEnabledFor(DEBUG):
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
    def _get_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
        fields = dotted_field.split(".")
        dict_ = event
        for field_ in fields:
            if field_ in dict_ and isinstance(dict_, dict):
                dict_ = dict_[field_]
            else:
                return None
        return dict_

    def _list_json_files_in_directory(self, directory: str) -> List[str]:
        """
        Collects all json and yaml files from a given directory and it's subdirectories.

        Parameters
        ----------
        directory: str
            Path to a directory which should be scanned

        Returns
        -------
        List[str]
            List of filenames in the given directory
        """
        valid_file_paths = []
        for root, _, files in os.walk(directory):
            for file_name in [
                file
                for file in files
                if (
                    (file.endswith(".json") or file.endswith(".yml"))
                    and not file.endswith("_test.json")
                )
            ]:
                valid_file_paths.append(os.path.join(root, file_name))
        return valid_file_paths
