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

from collections.abc import Sequence
from ipaddress import IPv4Address, IPv6Address, ip_address

from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.processor.network_comparison.rule import NetworkComparisonRule
from logprep.util.helper import FieldValue


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    def _prepare_event_values_for_match(
        self, values: Sequence, rule: ListComparisonRule, event: dict[str, FieldValue]
    ) -> list[IPv4Address | IPv6Address]:
        """Parse the source-field values as IP addresses, warning about invalid ones."""
        event_ips = []
        for value in values:
            try:
                event_ips.append(ip_address(value))
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
        return event_ips

    @staticmethod
    def _matches_compare_set(prepared_values: list, set_values: set) -> bool:
        """Return whether any parsed IP is contained in one of the networks."""
        return any(ip in network for network in set_values for ip in prepared_values)
