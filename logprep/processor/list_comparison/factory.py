"""This module contains a factory for ListComparison processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.list_comparison.processor import ListComparison


class ListComparisonFactory(BaseFactory):
    """Factory used to instantiate List Comparison processors."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> ListComparison:
        """
        Create a ListComparison processor based on the processor configuration
        specified in a given pipeline.yml
        """
        ListComparisonFactory._check_configuration(configuration)

        list_comparison = ListComparison(name, configuration.get('tree_config'), logger)
        list_comparison.add_rules_from_directory(configuration['rules'])

        return list_comparison

    @staticmethod
    def _check_configuration(configuration: dict):
        ListComparisonFactory._check_common_configuration('list_comparison', ['rules'], configuration)
