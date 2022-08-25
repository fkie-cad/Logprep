"""
processor strategies module

processor strategies are used to implement in one point how rules are processed in processors
this could be the order of specific or generic rules
"""
from abc import ABC, abstractmethod
from time import time
from typing import Callable, TYPE_CHECKING


if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc import Processor
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

    def process(self, event: dict, **kwargs):
        specific_tree = kwargs.get("specific_tree")
        generic_tree = kwargs.get("generic_tree")
        callback = kwargs.get("callback")
        processor_metrics = kwargs.get("processor_metrics")
        self._process_specific(event, specific_tree, callback, processor_metrics)
        self._process_generic(event, generic_tree, callback, processor_metrics)
        processor_metrics.number_of_processed_events += 1

    def _process_specific(
        self,
        event: dict,
        specific_tree: "RuleTree",
        callback: Callable,
        processor_metrics: "Processor.ProcessorMetrics",
    ):
        """method for processing specific rules"""
        for rule in specific_tree.get_matching_rules(event):
            begin = time()
            callback(event, rule)
            processing_time = time() - begin
            rule.metrics._number_of_matches += 1
            rule.metrics.update_mean_processing_time(processing_time)
            processor_metrics.update_mean_processing_time_per_event(processing_time)

    def _process_generic(
        self,
        event: dict,
        generic_tree: "RuleTree",
        callback: Callable,
        processor_metrics: "Processor.ProcessorMetrics",
    ):
        """method for processing generic rules"""
        for rule in generic_tree.get_matching_rules(event):
            begin = time()
            callback(event, rule)
            processing_time = time() - begin
            rule.metrics._number_of_matches += 1
            rule.metrics.update_mean_processing_time(processing_time)
            processor_metrics.update_mean_processing_time_per_event(processing_time)
