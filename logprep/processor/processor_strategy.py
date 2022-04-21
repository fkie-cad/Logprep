"""
processor strategies module

processor strategies are used to implement in one point how rules are processed in processors
this could be the order of specific or generic rules
"""
from abc import ABC, abstractmethod
from time import time
from typing import Callable, TYPE_CHECKING


if TYPE_CHECKING:
    from logprep.util.processor_stats import ProcessorStats
    from logprep.framework.rule_tree.rule_tree import RuleTree


class ProcessStrategy(ABC):
    """
    abstract class for strategies
    """

    @abstractmethod
    def process(self, event: dict, **kwargs):
        """abstract method for processing rules"""
        ...


class SpecificGenericProcessStrategy(ProcessStrategy):
    """
    Strategy to process rules in rule trees in the following order:
    specific_rules >> generic_rules
    """

    def process(self, event: dict, **kwargs):
        specific_rules = kwargs.get("specific_tree")
        generic_rules = kwargs.get("generic_tree")
        callback = kwargs.get("callback")
        processor_stats = kwargs.get("processor_stats")
        self._process_specific(event, specific_rules, callback, processor_stats)
        self._process_generic(event, generic_rules, callback, processor_stats)
        processor_stats.increment_processed_count()

    def _process_specific(
        self,
        event: dict,
        specific_tree: "RuleTree",
        callback: Callable,
        processor_stats: "ProcessorStats",
    ):
        """method for processing specific rules"""

        for rule in specific_tree.get_matching_rules(event):
            begin = time()
            callback(event, rule)
            processing_time = time() - begin
            idx = specific_tree.get_rule_id(rule)
            processor_stats.update_per_rule(idx, processing_time)

    def _process_generic(
        self,
        event: dict,
        generic_tree: "RuleTree",
        callback: Callable,
        processor_stats: "ProcessorStats",
    ):
        """method for processing generic rules"""
        for rule in generic_tree.get_matching_rules(event):
            begin = time()
            callback(event, rule)
            processing_time = time() - begin
            idx = generic_tree.get_rule_id(rule)
            processor_stats.update_per_rule(idx, processing_time)
