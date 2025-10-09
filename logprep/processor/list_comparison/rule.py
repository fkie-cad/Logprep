"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The list comparison enricher requires the additional field :code:`list_comparison`.
The mandatory keys under :code:`list_comparison` are :code:`source_fields`
(as list with one element) and :code:`target_field`. Former
is used to identify the field which is to be checked against the provided lists.
And the latter is used to define the parent field where the results should
be written to. Both fields can be dotted subfields.

Additionally, a list or array of lists can be provided underneath the
required field :code:`list_file_paths`.

In the following example, the field :code:`user_agent` will be checked against the provided list
(:code:`priviliged_users.txt`).
Assuming that the value :code:`non_privileged_user` will match the provided list,
the result of the list comparison (:code:`in_list`) will be added to the
target field :code:`List_comparison.example`.

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to compare a single field against a provided list.

    filter: 'user_agent'
    list_comparison:
        source_fields: ['user_agent']
        target_field: 'List_comparison.example'
        list_file_paths:
            - lists/privileged_users.txt
    description: '...'

.. note::

    Currently, it is not possible to check in more than one :code:`source_field` per rule.

.. autoclass:: logprep.processor.list_comparison.rule.ListComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import os.path
from ipaddress import ip_network
from string import Template
from typing import List, Optional

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.getter import GetterFactory


class ListComparisonRule(FieldManagerRule):
    """Check if documents match a filter."""

    _compare_sets: dict
    _ip_network_compare_sets: dict
    _compare_set_keys: list[str]

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for ListComparisonRule"""

        list_file_paths: List[str] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str))
        )
        """List of files. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: Processor - List Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - List Comparison list file paths Authenticity and Integrity

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

    def __init__(self, filter_rule: FilterExpression, config: dict, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self._compare_sets = {}
        self._ip_network_compare_sets = {}
        self._compare_set_keys = []

    def _get_list_search_base_path(self, list_search_base_path):
        if list_search_base_path is None:
            return self._config.list_search_base_path
        if self._config.list_search_base_path > list_search_base_path:
            return self._config.list_search_base_path
        return list_search_base_path

    def init_list_comparison(self, list_search_base_path: Optional[str] = None):
        """init method for list_comparison lists"""
        list_search_base_path = self._get_list_search_base_path(list_search_base_path)
        if list_search_base_path.startswith("http"):
            for list_path in self._config.list_file_paths:
                list_search_base_path_resolved = Template(list_search_base_path).substitute(
                    {**os.environ, **{"LOGPREP_LIST": list_path}}
                )
                content = GetterFactory.from_string(list_search_base_path_resolved).get()
                compare_elements = content.splitlines()
                file_elem_tuples = (elem for elem in compare_elements if not elem.startswith("#"))
                self._compare_sets.update({list_path: set(file_elem_tuples)})
            return
        absolute_list_paths = [
            list_path for list_path in self._config.list_file_paths if list_path.startswith("/")
        ]
        if not list_search_base_path.endswith("/"):
            list_search_base_path = list_search_base_path + "/"
        converted_absolute_list_paths = [
            list_search_base_path + list_path
            for list_path in self._config.list_file_paths
            if not list_path.startswith("/")
        ]
        list_paths = [*absolute_list_paths, *converted_absolute_list_paths]
        for list_path in list_paths:
            content = GetterFactory.from_string(list_path).get()
            compare_elements = content.splitlines()
            file_elem_tuples = (elem for elem in compare_elements if not elem.startswith("#"))
            string_elements = []
            network_elements = []
            for elem in file_elem_tuples:
                if "/" in elem:
                    try:
                        network_elements.append(ip_network(elem))
                    except ValueError:
                        string_elements.append(elem)
                else:
                    string_elements.append(elem)
            filename = os.path.basename(list_path)
            if string_elements:
                self._compare_sets.update({filename: set(string_elements)})
            if network_elements:
                self._ip_network_compare_sets.update({filename: set(network_elements)})

        compare_keys = list(self._compare_sets.keys())
        network_compare_keys = list(self._ip_network_compare_sets.keys())
        self._compare_set_keys = list(set(compare_keys + network_compare_keys))

    @property
    def compare_sets(self) -> dict:  # pylint: disable=missing-docstring
        return self._compare_sets

    @property
    def network_compare_sets(self) -> dict:  # pylint: disable=missing-docstring
        return self._ip_network_compare_sets

    @property
    def compare_set_keys(self) -> list[str]:  # pylint: disable=missing-docstring
        return self._compare_set_keys
