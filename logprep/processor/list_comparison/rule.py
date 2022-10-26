"""
This module is used to check if values within a specified field of a given log message
are elements of a given list.
"""

from pathlib import Path
from typing import List, Optional
from attrs import define, field, validators
from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule


class ListComparisonRule(Rule):
    """Check if documents match a filter."""

    _compare_sets: dict

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for ListComparisonRule"""

        check_field: str = field(validator=validators.instance_of(str))
        output_field: str = field(validator=validators.instance_of(str))
        list_file_paths: List[Path] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(Path)),
            converter=lambda paths: [Path(path) for path in paths],
        )
        list_search_base_path: Path = field(
            validator=validators.instance_of(Path), factory=Path, converter=Path
        )

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

    @property
    def check_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.check_field

    @property
    def list_comparison_output_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.output_field
