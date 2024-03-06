"""Abstract module for processors"""

from abc import abstractmethod
from logging import DEBUG, Logger
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from attr import define, field, validators

from logprep.abc.component import Component
from logprep.framework.rule_tree.rule_tree import RuleTree, RuleTreeType
from logprep.metrics.metrics import Metric
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
    ProcessingWarning,
)
from logprep.util import getter
from logprep.util.helper import (
    add_and_overwrite,
    add_field_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)
from logprep.util.json_handling import list_json_files_in_directory

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
                validators.deep_iterable(member_validator=validators.instance_of((str, dict))),
            ]
        )
        """List of rule locations to load rules from.
        In addition to paths to file directories it is possible to retrieve rules from a URI.
        For valid URI formats see :ref:`getters`.
        As last option it is possible to define entire rules with all their configuration parameters as list elements.
        """
        generic_rules: List[str] = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of((str, dict))),
            ]
        )
        """List of rule locations to load rules from.
        In addition to paths to file directories it is possible to retrieve rules from a URI.
        For valid URI formats see :ref:`getters`.
        As last option it is possible to define entire rules with all their configuration parameters as list elements.
        """
        tree_config: Optional[str] = field(
            default=None, validator=[validators.optional(validators.instance_of(str))]
        )
        """Path to a JSON file with a valid rule tree configuration.
        For string format see :ref:`getters`"""
        apply_multiple_times: Optional[bool] = field(
            default=False, validator=[validators.optional(validators.instance_of(bool))]
        )
        """Set if the processor should be applied multiple times. This enables further processing
        of an output with the same processor."""

    __slots__ = [
        "rule_class",
        "has_custom_tests",
        "_event",
        "_specific_tree",
        "_generic_tree",
    ]

    rule_class: "Rule"
    has_custom_tests: bool
    _event: dict
    _specific_tree: RuleTree
    _generic_tree: RuleTree
    _strategy = None

    def __init__(self, name: str, configuration: "Processor.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._specific_tree = RuleTree(
            processor_name=self.name,
            processor_config=self._config,
            rule_tree_type=RuleTreeType.SPECIFIC,
        )
        self._generic_tree = RuleTree(
            processor_name=self.name,
            processor_config=self._config,
            rule_tree_type=RuleTreeType.GENERIC,
        )
        self.load_rules(
            generic_rules_targets=self._config.generic_rules,
            specific_rules_targets=self._config.specific_rules,
        )
        self.has_custom_tests = False

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
    def rules(self):
        """Returns all rules

        Returns
        -------
        rules: list[Rule]
        """
        return [*self._generic_rules, *self._specific_rules]

    @property
    def metric_labels(self) -> dict:
        """Return metric labels."""
        return {
            "component": "processor",
            "description": self.describe(),
            "type": self._config.type,
            "name": self.name,
        }

    def process(self, event: dict):
        """Process a log event by calling the implemented `process` method of the
        strategy object set in  `_strategy` attribute.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """
        self._logger.debug(f"{self.describe()} processing event {event}")
        self._process_rule_tree(event, self._specific_tree)
        self._process_rule_tree(event, self._generic_tree)

    def _process_rule_tree(self, event: dict, tree: "RuleTree"):
        applied_rules = set()

        @Metric.measure_time()
        def _process_rule(rule, event):
            self._apply_rules_wrapper(event, rule)
            rule.metrics.number_of_processed_events += 1
            applied_rules.add(rule)
            return event

        def _process_rule_tree_multiple_times(tree, event):
            matching_rules = tree.get_matching_rules(event)
            while matching_rules:
                for rule in matching_rules:
                    _process_rule(rule, event)
                matching_rules = set(tree.get_matching_rules(event)).difference(applied_rules)

        def _process_rule_tree_once(tree, event):
            matching_rules = tree.get_matching_rules(event)
            for rule in matching_rules:
                _process_rule(rule, event)

        if self._config.apply_multiple_times:
            _process_rule_tree_multiple_times(tree, event)
        else:
            _process_rule_tree_once(tree, event)

    def _apply_rules_wrapper(self, event: dict, rule: "Rule"):
        try:
            self._apply_rules(event, rule)
        except ProcessingWarning as error:
            self._handle_warning_error(event, rule, error)
        except ProcessingCriticalError as error:
            raise error  # is needed to prevent wrapping it in itself
        except BaseException as error:
            raise ProcessingCriticalError(str(error), rule, event) from error
        if not hasattr(rule, "delete_source_fields"):
            return
        if rule.delete_source_fields:
            for dotted_field in rule.source_fields:
                pop_dotted_field_value(event, dotted_field)

    @abstractmethod
    def _apply_rules(self, event, rule): ...  # pragma: no cover

    def test_rules(self) -> dict:
        """Perform custom rule tests.

        Returns a dict with a list of test results as tuples containing a result and an expected
        result for each rule, i.e. {'RULE REPR': [('Result string', 'Expected string')]}
        Optional: Can be used in addition to regular rule tests.

        """

    @staticmethod
    def resolve_directories(rule_sources: list) -> list:
        """resolves directories to a list of files or rule definitions

        Parameters
        ----------
        rule_sources : list
            a list of files, directories or rule definitions

        Returns
        -------
        list
            a list of files and rule definitions
        """
        resolved_sources = []
        for rule_source in rule_sources:
            if isinstance(rule_source, dict):
                resolved_sources.append(rule_source)
                continue
            getter_instance = getter.GetterFactory.from_string(rule_source)
            if getter_instance.protocol == "file":
                if Path(getter_instance.target).is_dir():
                    paths = list_json_files_in_directory(getter_instance.target)
                    for file_path in paths:
                        resolved_sources.append(file_path)
                else:
                    resolved_sources.append(rule_source)
            else:
                resolved_sources.append(rule_source)
        return resolved_sources

    def load_rules(self, specific_rules_targets: List[str], generic_rules_targets: List[str]):
        """method to add rules from directories or urls"""
        specific_rules_targets = self.resolve_directories(specific_rules_targets)
        generic_rules_targets = self.resolve_directories(generic_rules_targets)
        for specific_rules_target in specific_rules_targets:
            rules = self.rule_class.create_rules_from_target(specific_rules_target, self.name)
            for rule in rules:
                self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_target in generic_rules_targets:
            rules = self.rule_class.create_rules_from_target(generic_rules_target, self.name)
            for rule in rules:
                self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            number_specific_rules = self._specific_tree.number_of_rules
            self._logger.debug(f"{self.describe()} loaded {number_specific_rules} specific rules")
            number_generic_rules = self._generic_tree.number_of_rules
            self._logger.debug(f"{self.describe()} loaded {number_generic_rules} generic rules")

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

    def _handle_warning_error(self, event, rule, error, failure_tags=None):
        tags = get_dotted_field_value(event, "tags")
        if failure_tags is None:
            failure_tags = rule.failure_tags
        if tags is None:
            add_and_overwrite(event, "tags", sorted(list({*failure_tags})))
        else:
            add_and_overwrite(event, "tags", sorted(list({*tags, *failure_tags})))
        if isinstance(error, ProcessingWarning):
            self._logger.warning(str(error))
        else:
            self._logger.warning(str(ProcessingWarning(str(error), rule, event)))

    def _has_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(lambda x: x[1] in [None, ""], source_field_dict.items())).keys()
        )
        if missing_fields:
            if rule.ignore_missing_fields:
                return True
            error = BaseException(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)
            return True
        return False

    def _write_target_field(self, event: dict, rule: "Rule", result: any) -> None:
        add_successful = add_field_to(
            event,
            output_field=rule.target_field,
            content=result,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
        if not add_successful:
            raise FieldExistsWarning(rule, event, [rule.target_field])

    def setup(self):
        super().setup()
        for rule in self.rules:
            _ = rule.metrics  # initialize metrics to show them on startup
