"""
NetworkComparison
=================

The `network_comparison` processor allows to compare values of source fields against lists provided
as files.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - networkcomparisonname:
        type: network_comparison
        rules:
            - tests/testdata/rules/rules
        list_search_base_path: /path/to/list/dir

.. autoclass:: logprep.processor.network_comparison.processor.NetworkComparison.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.network_comparison.rule
"""

import typing
from ipaddress import ip_address

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.base.rule import Rule
from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.network_comparison.rule import NetworkComparisonRule


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    def _get_lists_matching_with_values(
        self, rule: Rule, value_list: list, event: dict
    ) -> tuple[list, dict]:
        """Iterate over network lists, check if element is in any."""
        rule = typing.cast(NetworkComparisonRule, rule)
        list_matches: list = []
        try:
            dynamic_set = rule.get_dynamic_set(event)
        except Exception as error:
            raise ProcessingWarning(str(error), rule, event) from error

        for value in value_list:
            try:
                ip_address_object = ip_address(value)
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
                continue

            for compare_list, networks in dynamic_set.items():
                if compare_list in list_matches:
                    continue

                for network in networks:
                    if ip_address_object in network:
                        list_matches.append(compare_list)
                        break

        return list_matches, dynamic_set
