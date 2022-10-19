"""This module is used to get documents that match a clusterer filter."""

from typing import List, Union, Dict, Pattern
import re
from attrs import define, field, validators

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

    @define(kw_only=True)
    class Config:
        """RuleConfig for Clusterer"""

        target: str = field(validator=validators.instance_of(str))
        pattern: re.Pattern = field(
            validator=validators.instance_of(re.Pattern), converter=re.compile
        )
        repl: str = field(validator=validators.instance_of(str))

    # pylint: disable=C0111
    @property
    def target(self) -> str:
        return self._config.target

    @property
    def pattern(self) -> Pattern:
        return self._config.pattern

    @property
    def repl(self) -> str:
        return self._config.repl

    # pylint: enable=C0111

    @staticmethod
    def _check_if_clusterer_data_valid(rule: dict):
        for item in ("target", "pattern", "repl"):
            if item not in rule["clusterer"]:
                raise ClustererRuleError(f'Item "{item}" is missing in Clusterer-Rule')
            if not isinstance(rule["clusterer"][item], str):
                raise ClustererRuleError(
                    f'Value "{rule["clusterer"][item]}" in "{item}" ' f"is not a string"
                )
