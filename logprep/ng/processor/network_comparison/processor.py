"""
NetworkComparison
=================

The `ng_network_comparison` processor compares IP address values from source fields
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

.. autoclass:: logprep.ng.processor.network_comparison.processor.NetworkComparison.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.network_comparison.rule
"""

from collections.abc import Sequence
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address

from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.processor.network_comparison.rule import NetworkComparisonRule
from logprep.util.helper import FieldValue


class NetworkComparison(ListComparison):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = NetworkComparisonRule

    # TODO use generic type parameter for prepared values in the future
    def _prepare_event_values_for_match(  # type: ignore
        self, values: Sequence[FieldValue], rule: ListComparisonRule, event: dict[str, FieldValue]
    ) -> Sequence[IPv4Address | IPv6Address]:
        """Parse the source-field values as IP addresses, warning about invalid ones."""
        event_ips = []
        for value in values:
            try:
                if not isinstance(value, (str, int)):
                    raise ValueError(
                        f"{type(value)} is not supported in network comparisons: {value}"
                    )
                event_ips.append(ip_address(value))
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
        return event_ips

    @staticmethod
    def _matches_compare_set(  # type: ignore
        prepared_values: Sequence[IPv4Address | IPv6Address],
        set_values: set[IPv4Network | IPv6Network],
    ) -> bool:
        """Return whether any parsed IP is contained in one of the networks."""
        return any(ip in network for network in set_values for ip in prepared_values)
