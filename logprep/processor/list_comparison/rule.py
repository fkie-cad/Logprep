"""
This module is used to check if values within a specified field of a given log message
are elements of a given list.
"""

import os.path
from typing import Optional

from json import load
from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class ListComparisonRuleError(InvalidRuleDefinitionError):
    """Base class for ListComparison rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"ListComparison rule ({message})")


class InvalidListComparisonDefinition(ListComparisonRuleError):
    """Raise if ListComparison definition invalid."""

    def __init__(self, definition):
        message = f"The following ListComparison definition is invalid: {definition}"
        super().__init__(message)


class ListComparisonRule(Rule):
    """Check if documents match a filter."""

    allowed_cfg_fields = [
        "list_file_paths",
        "check_field",
        "output_field",
        "list_search_base_path",
    ]

    def __init__(self, filter_rule: FilterExpression, list_comparison_cfg: dict):
        """
        Instantiate ListComparisonRule based on a given filter and processor configuration.

        Parameters
        ----------
        filter_rule : FilterExpression
            Given lucene filter expression as a representation of the rule's logic.
        list_comparison_cfg: dict
            Configuration fields from a given pipeline that refer to the processor instance.
        """
        super().__init__(filter_rule)

        self._check_field = list_comparison_cfg["check_field"]
        self._list_comparison_output_field = list_comparison_cfg["output_field"]

        self._compare_sets = dict()
        self._config = list_comparison_cfg
        self.init_list_comparison()

    def init_list_comparison(self):
        for key in self._config.keys():
            if key.endswith("_paths"):
                file_paths = self._config[key]
                for list_path in file_paths:
                    with open(list_path, "r") as f:
                        compare_elements = f.read().splitlines()
                        file_elem_tuples = [
                            elem for elem in compare_elements if not elem.startswith("#")
                        ]
                        file_name = os.path.basename(list_path)
                        self._compare_sets[file_name] = set(file_elem_tuples)

    def __eq__(self, other: "ListComparisonRule") -> bool:
        return (other.filter == self._filter) and (self._check_field == other.check_field)

    def __hash__(self) -> int:
        return hash(repr(self))

    @property
    def compare_sets(self) -> dict:
        return self._compare_sets

    @property
    def check_field(self) -> str:
        return self._check_field

    @property
    def list_comparison_output_field(self) -> str:
        return self._list_comparison_output_field

    @staticmethod
    def _create_from_dict(rule: dict) -> "ListComparisonRule":
        ListComparisonRule._check_rule_validity(rule, "list_comparison")
        ListComparisonRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return ListComparisonRule(filter_expression, rule["list_comparison"])

    @staticmethod
    def _check_if_valid(rule: dict):
        """
        Check validity of a given rule file in relation to the processor configuration in the given pipeline.

        Parameters
        ----------
        rule : dict
            Current rule to be checked for configuration or field reference problems.

        """
        list_comparison_cfg = rule["list_comparison"]

        # check if the three needed config fields exist
        if (
            not len(
                [
                    key
                    for key in list_comparison_cfg.keys()
                    if key in ListComparisonRule.allowed_cfg_fields
                ]
            )
            <= 4
        ):
            raise InvalidListComparisonDefinition(
                f"Allowed config fields are: {', '.join(ListComparisonRule.allowed_cfg_fields)}, and of them"
                f" only one path field should be present."
            )

        # check if config contains unknown fields
        unknown_config_fields = [
            key
            for key in list_comparison_cfg.keys()
            if key not in ListComparisonRule.allowed_cfg_fields
        ]
        if len(unknown_config_fields) > 0:
            raise InvalidListComparisonDefinition(
                f"Unknown fields were given: {', '.join(unknown_config_fields)}"
            )

        # check validity of given fields
        for key in list_comparison_cfg.keys():
            # only check if paths are part of the configuration
            if key in ["list_file_paths"]:
                if len(list_comparison_cfg[key]) == 0:
                    raise InvalidListComparisonDefinition(
                        f"The rule should have at least one list configured"
                    )

                # iterate over all given files
                for path in list_comparison_cfg[key]:
                    if not isinstance(path, str) and not os.path.isfile(path):
                        raise InvalidListComparisonDefinition(f"{path} is not a existing file.")

            if key == "check_field":
                if not isinstance(list_comparison_cfg[key], str):
                    raise InvalidListComparisonDefinition("Check field must be 'str'")

            if key == "output_field":
                if not isinstance(list_comparison_cfg[key], str):
                    raise InvalidListComparisonDefinition("Output field must be 'str'")
