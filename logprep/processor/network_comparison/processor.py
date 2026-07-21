"""
NetworkComparison
=================

The `network_comparison` processor compares IP address values from source fields
against network lists loaded from local files or HTTP(S) targets. It supports the
same static and dynamic list path resolution as `list_comparison`.


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

from collections.abc import Iterable
from ipaddress import ip_address

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.processor.network_comparison.rule import NetworkComparisonRule


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    def _get_lists_matching_with_values(
        self, rule: ListComparisonRule, value_list: list, event: dict
    ) -> tuple[list[str], Iterable[str]]:
        """Return matching network-list identifiers and the evaluated compare set names.

        Invalid event values are reported as warnings and skipped. Dynamic list loading
        errors are converted to ``ProcessingWarning`` so the rule's failure tags are
        applied.
        """
        try:
            compare_sets = rule.get_compare_sets(event)
        except Exception as error:
            raise ProcessingWarning(str(error), rule, event) from error

        event_ips = []
        for value in value_list:
            try:
                event_ips.append(ip_address(value))
            except ValueError as error:
                self._handle_warning_error(event, rule, error)

        matches = [
            set_name
            for set_name, set_values in compare_sets.items()
            if any(ip in network for network in set_values for ip in event_ips)
        ]

        return matches, compare_sets.keys()
