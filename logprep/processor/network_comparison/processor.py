"""
NetworkComparison
=================

The `network_comparison` processor allows to compare values of source fields against lists provided
as files.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - listcomparisonname:
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

from ipaddress import ip_address

from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.network_comparison.rule import NetworkComparisonRule
from logprep.util.helper import get_dotted_field_value


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    def _list_comparison(self, rule: NetworkComparisonRule, event: dict) -> tuple[list, str]:
        """
        Check if field value violates block or allow list.
        Returns the result of the comparison (res_key), as well as a dictionary containing
        the result (key) and a list of filenames pertaining to said result (value).
        """

        # get IP that should be checked in the lists
        field_value = get_dotted_field_value(event, rule.source_fields[0])
        value_list = field_value if isinstance(field_value, list) else [field_value]

        # iterate over IP string lists and check if element is in any
        list_matches: list = []
        for field_value in value_list:
            self._compare_with_networks(list_matches, field_value, rule)

        # if matching list was found return it, otherwise return all list names
        if len(list_matches) == 0:
            return list(rule.compare_sets.keys()), "not_in_list"
        return list_matches, "in_list"

    @staticmethod
    def _compare_with_networks(list_matches: list, field_value: str, rule: NetworkComparisonRule):
        """Iterate over network lists, check if element is in any."""
        try:
            ip_address_object = ip_address(field_value)
        except ValueError:
            return

        for compare_list in rule.compare_sets:
            for network in rule.compare_sets[compare_list]:
                if compare_list in list_matches:
                    continue
                if ip_address_object in network:
                    list_matches.append(compare_list)
