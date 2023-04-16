"""
processor strategies module

processor strategies are used to implement in one point how rules are processed in processors
this could be the order of specific or generic rules
"""
from abc import ABC, abstractmethod
from functools import reduce
from time import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc.processor import Processor
    from logprep.framework.rule_tree.rule_tree import RuleTree


class ProcessStrategy(ABC):
    """
    abstract class for strategies
    """

    @abstractmethod
    def process(self, event: dict, **kwargs):
        """abstract method for processing rules"""
        ...  # pragma: no cover


class SpecificGenericProcessStrategy(ProcessStrategy):
    """
    Strategy to process rules in rule trees in the following order:
    specific_rules >> generic_rules
    """

    def __init__(self, apply_multiple_times=False):
        self._apply_multiple_times = apply_multiple_times

    def process(self, event: dict, **kwargs):
        specific_tree = kwargs.get("specific_tree")
        generic_tree = kwargs.get("generic_tree")
        callback = kwargs.get("callback")
        processor_metrics = kwargs.get("processor_metrics")
        processor_metrics.number_of_processed_events += 1
        self._process_specific(event, specific_tree, callback, processor_metrics)
        self._process_generic(event, generic_tree, callback, processor_metrics)

    def _process_specific(
        self,
        event: dict,
        specific_tree: "RuleTree",
        callback: Callable,
        processor_metrics: "Processor.ProcessorMetrics",
    ):
        """method for processing specific rules"""
        self._process_rule_tree(event, specific_tree, callback, processor_metrics)

    def _process_generic(
        self,
        event: dict,
        generic_tree: "RuleTree",
        callback: Callable,
        processor_metrics: "Processor.ProcessorMetrics",
    ):
        """method for processing generic rules"""
        self._process_rule_tree(event, generic_tree, callback, processor_metrics)

    def _process_rule_tree(
        self,
        event: dict,
        tree: "RuleTree",
        callback: Callable,
        processor_metrics: "Processor.ProcessorMetrics",
    ):
        applied_rules = set()

        def _process_rule(event, rule):
            begin = time()
            callback(event, rule)
            processing_time = time() - begin
            rule.metrics._number_of_matches += 1
            rule.metrics.update_mean_processing_time(processing_time)
            processor_metrics.update_mean_processing_time_per_event(processing_time)
            applied_rules.add(rule)
            return event

        if self._apply_multiple_times:
            matching_rules = tree.get_matching_rules(event)
            while matching_rules:
                reduce(_process_rule, (event, *matching_rules))
                matching_rules = set(tree.get_matching_rules(event)).difference(applied_rules)
        else:
            reduce(_process_rule, (event, *tree.get_matching_rules(event)))
