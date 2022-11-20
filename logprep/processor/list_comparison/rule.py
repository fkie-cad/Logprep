"""
List Comparison
===============

The list comparison enricher requires the additional field :code:`list_comparison`.
The mandatory keys under :code:`list_comparison` are :code:`source_fields` (as list with one element)
and :code:`target_field`. Former
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

    Currently it is not possible to check in more than one source_field per rule

"""
import warnings
from pathlib import Path
from typing import List, Optional
from attrs import define, field, validators
from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class ListComparisonRule(FieldManagerRule):
    """Check if documents match a filter."""

    _compare_sets: dict

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for ListComparisonRule"""

        list_file_paths: List[Path] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(Path)),
            converter=lambda paths: [Path(path) for path in paths],
        )
        """List of files in relative or absolute notation"""
        list_search_base_path: Path = field(
            validator=validators.instance_of(Path), factory=Path, converter=Path
        )
        """Base Path from where to find relative files from :code:`list_file_paths` (Optional)"""

    def __init__(self, filter_rule: FilterExpression, config: dict):
        super().__init__(filter_rule, config)
        self._compare_sets = {}

    def _get_list_search_base_path(self, list_search_base_path):
        if list_search_base_path is None:
            return self._config.list_search_base_path
        list_search_base_path = Path(list_search_base_path)
        if self._config.list_search_base_path > list_search_base_path:
            return self._config.list_search_base_path
        return list_search_base_path

    def init_list_comparison(self, list_search_base_path: Optional[str] = None):
        """init method for list_comparision lists"""
        list_search_base_path = self._get_list_search_base_path(list_search_base_path)
        absolute_list_paths = [
            list_path for list_path in self._config.list_file_paths if list_path.is_absolute()
        ]
        converted_absolute_list_paths = [
            list_search_base_path / list_path
            for list_path in self._config.list_file_paths
            if not list_path.is_absolute()
        ]
        list_paths = [*absolute_list_paths, *converted_absolute_list_paths]
        for list_path in list_paths:
            compare_elements = list_path.read_text().splitlines()
            file_elem_tuples = [elem for elem in compare_elements if not elem.startswith("#")]
            self._compare_sets.update({list_path.name: set(file_elem_tuples)})

    @property
    def compare_sets(self) -> dict:  # pylint: disable=missing-docstring
        return self._compare_sets

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("list_comparison", {}).get("check_field") is not None:
            source_field_value = pop_dotted_field_value(rule, "list_comparison.check_field")
            add_and_overwrite(rule, "list_comparison.source_fields", [source_field_value])
            warnings.warn(
                (
                    "list_comparison.check_field is deprecated. "
                    "Use list_comparison.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("list_comparison", {}).get("output_field") is not None:
            target_field_value = pop_dotted_field_value(rule, "list_comparison.output_field")
            add_and_overwrite(rule, "list_comparison.target_field", target_field_value)
            warnings.warn(
                (
                    "list_comparison.output_field is deprecated. "
                    "Use list_comparison.target_field instead"
                ),
                DeprecationWarning,
            )
