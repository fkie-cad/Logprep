"""
NetworkComparison
=================

The `ng_network_comparison` processor allows to compare values of source fields against lists provided
as files.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - networkcomparisonname:
        type: ng_network_comparison
        rules:
            - tests/testdata/rules/rules
        list_search_base_path: /path/to/list/dir

.. autoclass:: logprep.ng.processor.network_comparison.processor.NetworkComparison.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.ng.processor.network_comparison.rule
"""

from ipaddress import ip_address

from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.processor.network_comparison.rule import NetworkComparisonRule


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    def _get_lists_matching_with_values(
        self, rule: NetworkComparisonRule, value_list: list, event: dict
    ) -> list:
        """Iterate over network lists, check if element is in any."""
        list_matches: list = []
        for value in value_list:
            try:
                ip_address_object = ip_address(value)
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
                continue

            for compare_list in rule.compare_sets:
                for network in rule.compare_sets[compare_list]:
                    if compare_list in list_matches:
                        continue
                    if ip_address_object in network:
                        list_matches.append(compare_list)
        return list_matches
