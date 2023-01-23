"""Abstract module for processors"""
import copy
from abc import abstractmethod
from logging import DEBUG, Logger
from multiprocessing import current_process
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from attr import define, field, validators

from logprep.abc.component import Component
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric import Metric, calculate_new_average
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.processor_strategy import SpecificGenericProcessStrategy
from logprep.util import getter
from logprep.util.helper import pop_dotted_field_value, get_dotted_field_value, add_and_overwrite
from logprep.util.json_handling import list_json_files_in_directory
from logprep.util.time_measurement import TimeMeasurement

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule  # pragma: no cover


class Processor(Component):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config(Component.Config):
        """Common Configurations"""

        specific_rules: List[str] = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ]
        )
        """List of rule locations to load rules from.
        In addition to paths to file directories it is possible to retrieve rules from a URI.
        For valid URI formats see :ref:`getters`.
        """
        generic_rules: List[str] = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ]
        )
        """List of rule locations to load rules from.
        In addition to paths to file directories it is possible to retrieve rules from a URI.
        For valid URI formats see :ref:`getters`.
        """
        tree_config: Optional[str] = field(
            default=None, validator=[validators.optional(validators.instance_of(str))]
        )
        """Path to a JSON file with a valid rule tree configuration.
        For string format see :ref:`getters`"""

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

    rule_class: "Rule"
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
        self.load_rules(
            generic_rules_targets=self._config.generic_rules,
            specific_rules_targets=self._config.specific_rules,
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
        try:
            self._apply_rules(event, rule)
        except ProcessingWarning as error:
            self._handle_warning_error(event, rule, error)
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

    @staticmethod
    def resolve_directories(rule_paths: list) -> list:
        resolved_paths = []
        for rule_path in rule_paths:
            getter_instance = getter.GetterFactory.from_string(rule_path)
            if getter_instance.protocol == "file":
                if Path(getter_instance.target).is_dir():
                    paths = list_json_files_in_directory(getter_instance.target)
                    for file_path in paths:
                        resolved_paths.append(file_path)
                else:
                    resolved_paths.append(rule_path)
            else:
                resolved_paths.append(rule_path)
        return resolved_paths

    def load_rules(self, specific_rules_targets: List[str], generic_rules_targets: List[str]):
        """method to add rules from directories or urls"""
        specific_rules_targets = self.resolve_directories(specific_rules_targets)
        generic_rules_targets = self.resolve_directories(generic_rules_targets)
        for specific_rules_target in specific_rules_targets:
            rules = self.rule_class.create_rules_from_target(specific_rules_target)
            for rule in rules:
                self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_target in generic_rules_targets:
            rules = self.rule_class.create_rules_from_target(generic_rules_target)
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
        if isinstance(error, ProcessingWarning):
            raise error
        raise ProcessingWarning(str(error)) from error

    def _check_for_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(lambda x: x[1] in [None, ""], source_field_dict.items())).keys()
        )
        if missing_fields:
            error = BaseException(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)
