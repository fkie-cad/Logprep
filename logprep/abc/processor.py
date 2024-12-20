"""Abstract module for processors"""

import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from attr import define, field, validators

from logprep.abc.component import Component
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metrics import Metric
from logprep.processor.base.exceptions import (
    ProcessingCriticalError,
    ProcessingError,
    ProcessingWarning,
)
from logprep.util import getter
from logprep.util.helper import (
    add_and_overwrite,
    add_fields_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)
from logprep.util.json_handling import list_json_files_in_directory

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule  # pragma: no cover

logger = logging.getLogger("Processor")


@define(kw_only=True)
class ProcessorResult:
    """
    Result object to be returned by every processor. It contains the processor name, created data
    and errors (incl. warnings).

    Parameters
    ----------


    processor_name : str
        The name of the processor
    event: Optional[dict]
        A reference to the event that was processed
    data : Optional[list]
        The generated extra data
    errors : Optional[list]
        The errors that occurred during processing
    warnings : Optional[list]
        The warnings that occurred during processing
    """

    data: list = field(validator=validators.instance_of(list), factory=list)
    """ The generated extra data """
    errors: list = field(
        validator=validators.deep_iterable(
            member_validator=validators.instance_of(ProcessingError),
            iterable_validator=validators.instance_of(list),
        ),
        factory=list,
    )
    """ The errors that occurred during processing """
    warnings: list = field(
        validator=validators.deep_iterable(
            member_validator=validators.instance_of(ProcessingWarning),
            iterable_validator=validators.instance_of(list),
        ),
        factory=list,
    )
    """ The warnings that occurred during processing """
    processor_name: str = field(validator=validators.instance_of(str))
    """ The name of the processor """
    event: dict = field(validator=validators.optional(validators.instance_of(dict)), default=None)
    """ A reference to the event that was processed """


class Processor(Component):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config(Component.Config):
        """Common Configurations"""

        rules: List[str] = field(
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
        """Path to a JSON file with a valid :ref:`Rule Tree Configuration`.
        For string format see :ref:`getters`."""
        apply_multiple_times: Optional[bool] = field(
            default=False, validator=[validators.optional(validators.instance_of(bool))]
        )
        """Set if the processor should be applied multiple times. This enables further processing
        of an output with the same processor."""

    __slots__ = [
        "rule_class",
        "_event",
        "_rule_tree",
        "result",
        "_bypass_rule_tree",
    ]

    rule_class: "Rule"
    _event: dict
    _rule_tree: RuleTree
    _strategy = None
    _bypass_rule_tree: bool
    result: ProcessorResult

    def __init__(self, name: str, configuration: "Processor.Config"):
        super().__init__(name, configuration)
        self._rule_tree = RuleTree(config=self._config.tree_config)
        self.load_rules(rules_targets=self._config.rules)
        self.result = None
        self._bypass_rule_tree = False
        if os.environ.get("LOGPREP_BYPASS_RULE_TREE"):
            self._bypass_rule_tree = True
            logger.debug("Bypassing rule tree for processor %s", self.name)

    @property
    def rules(self):
        """Returns all rules

        Returns
        -------
        rules: list[Rule]
        """
        return self._rule_tree.rules

    @property
    def metric_labels(self) -> dict:
        """Return metric labels."""
        return {
            "component": "processor",
            "description": self.describe(),
            "type": self._config.type,
            "name": self.name,
        }

    def process(self, event: dict) -> ProcessorResult:
        """Process a log event.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        Returns
        -------
        ProcessorResult
            A ProcessorResult object containing the processed event, errors,
            extra data and a list of target outputs.

        """
        self.result = ProcessorResult(processor_name=self.name, event=event)
        logger.debug(f"{self.describe()} processing event {event}")
        if self._bypass_rule_tree:
            self._process_all_rules(event)
            return self.result
        self._process_rule_tree(event, self._rule_tree)
        return self.result

    def _process_all_rules(self, event: dict):

        @Metric.measure_time()
        def _process_rule(rule, event):
            self._apply_rules_wrapper(event, rule)
            rule.metrics.number_of_processed_events += 1
            return event

        for rule in self.rules:
            if rule.matches(event):
                _process_rule(rule, event)

    def _process_rule_tree(self, event: dict, tree: RuleTree):
        applied_rules = set()

        @Metric.measure_time()
        def _process_rule(rule, event):
            self._apply_rules_wrapper(event, rule)
            rule.metrics.number_of_processed_events += 1
            applied_rules.add(rule)
            return event

        def _process_rule_tree_multiple_times(tree: RuleTree, event: dict):
            matching_rules = tree.get_matching_rules(event)
            while matching_rules:
                for rule in matching_rules:
                    _process_rule(rule, event)
                matching_rules = set(tree.get_matching_rules(event)).difference(applied_rules)

        def _process_rule_tree_once(tree: RuleTree, event: dict):
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
            self.result.errors.append(error)  # is needed to prevent wrapping it in itself
            event.clear()
        except Exception as error:  # pylint: disable=broad-except
            self.result.errors.append(ProcessingCriticalError(str(error), rule))
            event.clear()
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

    def load_rules(self, rules_targets: List[str]):
        """method to add rules from directories or urls"""
        rules_targets = self.resolve_directories(rules_targets)
        for rules_target in rules_targets:
            rules = self.rule_class.create_rules_from_target(rules_target, self.name)
            for rule in rules:
                self._rule_tree.add_rule(rule)
        if logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            number_rules = self._rule_tree.number_of_rules
            logger.debug(f"{self.describe()} loaded {number_rules} rules")

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
            new_field = {"tags": sorted(list({*failure_tags}))}
        else:
            new_field = {"tags": sorted(list({*tags, *failure_tags}))}
        add_and_overwrite(event, new_field, rule)
        if isinstance(error, ProcessingWarning):
            if error.tags:
                tags = tags if tags else []
                new_field = {"tags": sorted(list({*error.tags, *tags, *failure_tags}))}
                add_and_overwrite(event, new_field, rule)
            self.result.warnings.append(error)
        else:
            self.result.warnings.append(ProcessingWarning(str(error), rule, event))

    def _has_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(lambda x: x[1] in [None, ""], source_field_dict.items())).keys()
        )
        if missing_fields:
            if rule.ignore_missing_fields:
                return True
            error = Exception(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)
            return True
        return False

    def _write_target_field(self, event: dict, rule: "Rule", result: any) -> None:
        add_fields_to(
            event,
            fields={rule.target_field: result},
            merge_with_target=rule.merge_with_target,
            overwrite_target=rule.overwrite_target,
        )

    def setup(self):
        super().setup()
        for rule in self.rules:
            _ = rule.metrics  # initialize metrics to show them on startup
