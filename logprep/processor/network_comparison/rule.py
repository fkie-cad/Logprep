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
from typing import Optional, List

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.getter import HttpGetter


class NetworkComparisonRule(ListComparisonRule):
    """Check if documents match a filter."""

    _compare_sets: dict

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for NetworkComparisonRule"""

        list_file_paths: List[str] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str))
        )
        """List of files. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """
        list_search_base_path: str = field(validator=validators.instance_of(str), factory=str)
        """Base Path from where to find relative files from :code:`list_file_paths`.
        You can also pass a template with keys from environment,
        e.g.,  :code:`${<your environment variable>}`. The special key :code:`${LOGPREP_LIST}`
        will be filled by this processor. """
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

    def init_list_comparison(self, list_search_base_path: Optional[str] = None) -> None:
        """init method for list_comparison lists"""
        super().init_list_comparison(list_search_base_path)
        self._convert_compare_sets_to_networks()

    def _update_compare_sets_via_http(self, http_getter: HttpGetter, list_path: str) -> None:
        super()._update_compare_sets_via_http(http_getter, list_path)
        self._convert_compare_sets_to_networks()

    def _convert_compare_sets_to_networks(self) -> None:
        network_comparison: dict = {}
        for list_name, compare_strings in self._compare_sets.items():
            if compare_strings:
                network_comparison[list_name] = set()
                for compare_string in compare_strings:
                    network_comparison[list_name].add(ip_network(compare_string))
        self._compare_sets = network_comparison
