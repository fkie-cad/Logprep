"""
This module contains functionality for checking if values exist or not exist in file lists.
This processor implements black- and whitelisting capabilities.
"""
from logging import Logger
from typing import List

from logprep.abc import Processor
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.helper import add_field_to


class ListComparisonError(BaseException):
    """Base class for ListComparison related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"ListComparison ({name}): {message}")


class DuplicationError(ListComparisonError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields could not be written, because "
            "one or more subfields existed and could not be extended: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class ListComparison(Processor):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = ListComparisonRule

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        """
        Initializes the list_comparison processor.

        Parameters
        ----------
        name : str
            Name of the list_comparison processor (as referred to in the pipeline).
        configuration : dict
            Configuration object containing all necessary parameters
        logger : Logger
            Standard logger.
        """
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._list_search_base_dir = configuration.get("list_search_base_path")

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
            output_field = f"{ rule.list_comparison_output_field }.{ comparison_key }"
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
        field_value = self._get_dotted_field_value(event, rule.check_field)

        # iterate over lists and check if element is in any
        list_matches = []
        for compare_list in rule.compare_sets.keys():
            if field_value in rule.compare_sets[compare_list]:
                list_matches.append(compare_list)

        # if matching list was found return it, otherwise return all list names
        if len(list_matches) == 0:
            return list(rule.compare_sets.keys()), "not_in_list"
        return list_matches, "in_list"
