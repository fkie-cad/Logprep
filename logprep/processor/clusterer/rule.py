"""This module is used to get documents that match a clusterer filter."""

from typing import List, Union, Dict, Pattern
import re

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule


class ClustererRuleError(BaseException):
    """Base class for Clusterer rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"Clusterer rule ({message}): ")


class InvalidClusteringDefinition(ClustererRuleError):
    """Raise if clustering definition is invalid."""

    def __init__(self, definition: str):
        message = f"The following clustering definition is invalid: {definition}"
        super().__init__(message)


class ClustererRule(Rule):
    """Check if documents match a filter."""

    def __init__(
        self,
        filter_rule: FilterExpression,
        clusterer_cfg: dict,
        tests: Union[List[Dict[str, str]], Dict[str, str]] = None,
    ):
        super().__init__(filter_rule)
        self._target = clusterer_cfg["target"]
        self._pattern = re.compile(clusterer_cfg["pattern"])
        self._repl = clusterer_cfg["repl"]

        if isinstance(tests, list):
            self._tests = tests
        elif isinstance(tests, dict):
            self._tests = [tests]
        else:
            self._tests = []

    def __eq__(self, other: "ClustererRule") -> bool:
        filter_equal = self._filter == other.filter
        target_equal = self._target == other.target
        pattern_equal = self._pattern == other.pattern
        repl_equal = self._repl == other.repl
        return filter_equal and target_equal and pattern_equal and repl_equal

    # pylint: disable=C0111
    @property
    def target(self) -> str:
        return self._target

    @property
    def pattern(self) -> Pattern:
        return self._pattern

    @property
    def repl(self) -> str:
        return self._repl

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "ClustererRule":
        ClustererRule._check_rule_validity(rule, "clusterer", optional_keys={"tests"})
        ClustererRule._check_if_clusterer_data_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return ClustererRule(filter_expression, rule["clusterer"], rule.get("tests"))

    @staticmethod
    def _check_if_clusterer_data_valid(rule: dict):
        for item in ("target", "pattern", "repl"):
            if item not in rule["clusterer"]:
                raise ClustererRuleError(f'Item "{item}" is missing in Clusterer-Rule')
            if not isinstance(rule["clusterer"][item], str):
                raise ClustererRuleError(
                    f'Value "{rule["clusterer"][item]}" in "{item}" ' f"is not a string"
                )
