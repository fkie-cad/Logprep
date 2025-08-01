"""Abstract module for processors"""

import logging
import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Type

from attrs import define, field, validators

from logprep.abc.component import Component
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metrics import Metric
from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import ProcessingCriticalError, ProcessingWarning
from logprep.util.helper import add_and_overwrite, add_fields_to, get_dotted_field_value
from logprep.util.rule_loader import RuleLoader

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule  # pragma: no cover

logger = logging.getLogger("Processor")


class Processor(Component):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config(Component.Config):
        """Common Configurations"""

        rules: list[str] = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of((str, dict))),
            ]
        )
        """List of rule locations to load rules from.
        In addition to paths to file directories it is possible to retrieve rules from a URI.
        For valid URI formats see :ref:`getters`.
        As last option it is possible to define entire rules with all their configuration parameters
        as list elements.
        """
        tree_config: str | None = field(
            default=None, validator=validators.instance_of((str, type(None)))
        )
        """Path to a JSON file with a valid :ref:`Rule Tree Configuration`.
        For string format see :ref:`getters`."""
        apply_multiple_times: bool = field(default=False, validator=validators.instance_of(bool))
        """Set if the processor should be applied multiple times. This enables further processing
        of an output with the same processor."""

    __slots__ = [
        "_event",
        "_rule_tree",
        "_bypass_rule_tree",
    ]

    rule_class: ClassVar[Type["Rule"] | None] = None
    _event: LogEvent
    _rule_tree: RuleTree
    _strategy = None
    _bypass_rule_tree: bool

    def __init__(self, name: str, configuration: "Processor.Config") -> None:
        super().__init__(name, configuration)
        self._rule_tree = RuleTree(config=self._config.tree_config)
        self.load_rules(rules_targets=self._config.rules)
        self._bypass_rule_tree = False
        if os.environ.get("LOGPREP_BYPASS_RULE_TREE"):
            self._bypass_rule_tree = True
            logger.debug("Bypassing rule tree for processor %s", self.name)

    @property
    def rules(self) -> list["Rule"]:
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

    def process(self, event: LogEvent) -> LogEvent:
        """Process a log event.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        Returns
        -------
        LogEvent
            A LogEvent object containing the processed event, errors, warnings and
            extra data

        """
        self._event = event
        logger.debug("%s processing event %s", self.describe(), event)
        if self._bypass_rule_tree:
            self._process_all_rules(event.data)
            return self._event
        self._process_rule_tree(event.data, self._rule_tree)
        return self._event

    def _process_all_rules(self, event: dict) -> None:

        @Metric.measure_time()
        def _process_rule(rule, event):
            self._apply_rules_wrapper(event, rule)
            rule.metrics.number_of_processed_events += 1
            return event

        for rule in self.rules:
            if rule.matches(event):
                _process_rule(rule, event)

    def _process_rule_tree(self, event: dict, tree: RuleTree) -> None:
        applied_rules = set()

        @Metric.measure_time()
        def _process_rule(rule, event):
            self._apply_rules_wrapper(event, rule)
            rule.metrics.number_of_processed_events += 1
            applied_rules.add(rule)
            return event

        def _process_rule_tree_multiple_times(tree: RuleTree, event: dict) -> None:
            matching_rules = tree.get_matching_rules(event)
            while matching_rules:
                for rule in matching_rules:
                    _process_rule(rule, event)
                matching_rules = set(tree.get_matching_rules(event)).difference(applied_rules)

        def _process_rule_tree_once(tree: RuleTree, event: dict) -> None:
            matching_rules = tree.get_matching_rules(event)
            for rule in matching_rules:
                _process_rule(rule, event)

        if self._config.apply_multiple_times:
            _process_rule_tree_multiple_times(tree, event)
        else:
            _process_rule_tree_once(tree, event)

    def _apply_rules_wrapper(self, event: dict, rule: "Rule") -> None:
        try:
            self._apply_rules(event, rule)
        except ProcessingWarning as error:
            self._handle_warning_error(event, rule, error)
        except ProcessingCriticalError as error:
            if self._event is None:
                raise error
            self._event.errors.append(error)  # is needed to prevent wrapping it in itself
            event.clear()
        except Exception as error:  # pylint: disable=broad-except
            if self._event is None:
                raise error
            self._event.errors.append(ProcessingCriticalError(str(error), rule))
            event.clear()
        if not hasattr(rule, "delete_source_fields"):
            return
        if rule.delete_source_fields:
            for dotted_field in rule.source_fields:
                self._event.pop_dotted_field_value(dotted_field)

    @abstractmethod
    def _apply_rules(self, event: dict, rule: "Rule"): ...  # pragma: no cover

    def test_rules(self) -> dict | None:
        """Perform custom rule tests.

        Returns a dict with a list of test results as tuples containing a result and an expected
        result for each rule, i.e. {'RULE REPR': [('Result string', 'Expected string')]}
        Optional: Can be used in addition to regular rule tests.

        """

    def load_rules(self, rules_targets: list[str | dict]) -> None:
        """method to add rules from directories or urls"""
        try:
            rules = RuleLoader(rules_targets, self.name).rules
        except ValueError as error:
            logger.error("Loading rules from %s failed: %s ", rules_targets, error)
            raise error
        for rule in rules:
            self._rule_tree.add_rule(rule)
        if logger.isEnabledFor(logging.DEBUG):
            number_rules = self._rule_tree.number_of_rules
            logger.debug("%s loaded %s rules", self.describe(), number_rules)

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

    def _handle_warning_error(
        self, event: dict, rule: "Rule", error: Exception, failure_tags: list | None = None
    ) -> None:
        tags = get_dotted_field_value(event, "tags")
        if failure_tags is None:
            failure_tags = rule.failure_tags
        if tags is None:
            new_field = {"tags": sorted(list({*failure_tags}))}
        else:
            tags_list = tags if isinstance(tags, list) else [tags]
            new_field = {"tags": sorted(list({*tags_list, *failure_tags}))}
        add_and_overwrite(event, new_field, rule)
        if isinstance(error, ProcessingWarning):
            if error.tags:
                tags = tags if tags is not None else []
                tags_list = tags if isinstance(tags, list) else [tags]
                new_field = {"tags": sorted(list({*error.tags, *tags_list, *failure_tags}))}
                add_and_overwrite(event, new_field, rule)
            self._event.warnings.append(error)
        else:
            self._event.warnings.append(ProcessingWarning(str(error), rule, event))

    def _has_missing_values(self, event: dict, rule: "Rule", source_field_dict: dict) -> bool:
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

    def _write_target_field(self, event: dict, rule: "Rule", result: Any) -> None:
        add_fields_to(
            event,
            fields={rule.target_field: result},
            merge_with_target=rule.merge_with_target,
            overwrite_target=rule.overwrite_target,
        )

    def setup(self) -> None:
        super().setup()
        for rule in self.rules:
            _ = rule.metrics  # initialize metrics to show them on startup
