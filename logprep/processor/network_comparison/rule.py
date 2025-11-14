"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The network comparison enricher can match IPs to IP strings and networks in CIDR notation.

The network comparison enricher requires the additional field :code:`network_comparison`.
The mandatory keys under :code:`network_comparison` are :code:`source_fields`
(as list with one element) and :code:`target_field`. Former
is used to identify the field which is to be checked against the provided lists.
And the latter is used to define the parent field where the results should
be written to. Both fields can be dotted subfields.

Additionally, a list or array of lists can be provided underneath the
required field :code:`list_file_paths`.

In the following example, the field :code:`ip` will be checked against the provided list
(:code:`networks.txt`).
Assuming that the value :code:`127.0.0.1` will match the provided list,
the result of the network comparison (:code:`in_list`) will be added to the
target field :code:`network_comparison.example`.

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to compare a single field against a provided list.

    filter: 'ip'
    network_comparison:
        source_fields: ['ip']
        target_field: 'network_comparison.example'
        list_file_paths:
            - lists/networks.txt
    description: '...'

.. note::

    Currently, it is not possible to check in more than one :code:`source_field` per rule.

.. autoclass:: logprep.processor.network_comparison.rule.NetworkComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from ipaddress import ip_network
from typing import Optional

from logprep.processor.list_comparison.rule import ListComparisonRule


class NetworkComparisonRule(ListComparisonRule):
    """Check if documents match a filter."""

    _compare_sets: dict

    def init_list_comparison(self, list_search_base_path: Optional[str] = None) -> None:
        """init method for list_comparison lists"""
        super().init_list_comparison(list_search_base_path)
        network_comparison: dict = {}
        for list_name, compare_strings in self._compare_sets.items():
            if compare_strings:
                network_comparison[list_name] = set()
                for compare_string in compare_strings:
                    try:
                        network_comparison[list_name].add(ip_network(compare_string))
                    except ValueError:
                        pass
        self._compare_sets = network_comparison
