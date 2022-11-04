"""
ListComparison
--------------

The `list_comparison` processor allows to compare values of source fields against lists provided
as files.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - listcomparisonname:
        type: list_comparison
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        list_search_base_path: /path/to/list/dir
"""
from logging import Logger

from attr import define, field

from logprep.abc import Processor
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import directory_validator
from logprep.processor.base.exceptions import DuplicationError


class ListComparisonError(BaseException):
    """Base class for ListComparison related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"ListComparison ({name}): {message}")


class ListComparison(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """ListComparison config"""

        list_search_base_path: str = field(validator=directory_validator)
        """Relative list paths in rules will be relative to this path if this is set.
        This parameter is optional."""

    rule_class = ListComparisonRule

    def __init__(self, name: str, configuration: "Processor.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._init_rules_list_comparison()

    def _init_rules_list_comparison(self):
        for rule in [*self._specific_rules, *self._generic_rules]:
            rule.init_list_comparison(self._config.list_search_base_path)

    def _apply_rules(self, event, rule):
        """
        Apply matching rule to given log event.
        In the process of doing so, add the result of comparing
        the log with a given list to the specified subfield. This subfield will contain
        a list of list comparison results that might be based on multiple rules.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied list comparison rule.

        """

        comparison_result, comparison_key = self._list_comparison(rule, event)

        if comparison_result is not None:
            output_field = f"{ rule.target_field }.{ comparison_key }"
            field_possible = add_field_to(event, output_field, comparison_result, True)
            if not field_possible:
                raise DuplicationError(self.name, [output_field])

    def _list_comparison(self, rule: ListComparisonRule, event: dict):
        """
        Check if field value violates block or allow list.
        Returns the result of the comparison (res_key), as well as a dictionary containing
        the result (key) and a list of filenames pertaining to said result (value).
        """

        # get value that should be checked in the lists
        field_value = get_dotted_field_value(event, rule.source_fields[0])

        # iterate over lists and check if element is in any
        list_matches = []
        for compare_list in rule.compare_sets:
            if field_value in rule.compare_sets[compare_list]:
                list_matches.append(compare_list)

        # if matching list was found return it, otherwise return all list names
        if len(list_matches) == 0:
            return list(rule.compare_sets.keys()), "not_in_list"
        return list_matches, "in_list"
