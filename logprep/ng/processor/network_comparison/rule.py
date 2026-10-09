"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The |PROCESSOR_NAME| can match IPs to IP strings and networks in CIDR notation.

The |PROCESSOR_NAME| requires the additional field :code:`network_comparison`.
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

.. autoclass:: logprep.ng.processor.network_comparison.rule.NetworkComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:


Examples for network_comparison:
--------------------------------

.. datatemplate:import-module:: tests.unit.ng.processor.network_comparison.test_network_comparison
   :template: testcase-renderer.tmpl

"""

from ipaddress import IPv4Network, IPv6Network, ip_network

from logprep.ng.processor.list_comparison.rule import ListComparisonRule


class NetworkComparisonRule(ListComparisonRule):
    """Check if documents match a filter."""

    def _transform_and_filter_list_element(  # type: ignore
        self,
        elem: str,
    ) -> IPv4Network | IPv6Network | None:
        transformed = super()._transform_and_filter_list_element(elem)
        if transformed is not None:
            return ip_network(transformed)
        return None
