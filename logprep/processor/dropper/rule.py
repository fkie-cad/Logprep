"""This module is used to drop specified fields that match a dropper filter."""

from typing import List
from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class DropperRuleError(InvalidRuleDefinitionError):
    """Base class for Dropper rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"Dropper rule ({message}): ")


class InvalidDropperDefinition(DropperRuleError):
    """Raise if Dropper definition invalid."""

    def __init__(self, definition):
        message = f"The following Dropper definition is invalid: {definition}"
        super().__init__(message)


class DropperRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, drop: List[str], drop_full=True):
        super().__init__(filter_rule)
        self._fields_to_drop = drop
        self._drop_full = drop_full

    def __eq__(self, other: "DropperRule") -> bool:
        return (
            (other.filter == self._filter)
            and (self._fields_to_drop == other.fields_to_drop)
            and (self._drop_full == other.drop_full)
        )

    # pylint: disable=C0111
    @property
    def fields_to_drop(self) -> List[str]:
        return self._fields_to_drop

    @property
    def drop_full(self) -> bool:
        return self._drop_full

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "DropperRule":
        DropperRule._check_rule_validity(rule, "drop", optional_keys={"drop_full"})
        DropperRule._check_if_drops_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return DropperRule(filter_expression, rule["drop"], rule.get("drop_full", True))

    @staticmethod
    def _check_if_drops_valid(rule: dict):
        if not isinstance(rule["drop"], list):
            raise InvalidDropperDefinition(f'Drop value "{rule["drop"]}" is not a list!')

        if not all(isinstance(value, str) for value in rule["drop"]):
            raise InvalidDropperDefinition(f'Drop values {rule["drop"]} are not a list of strings!')

        if not isinstance(rule.get("drop_full", True), bool):
            raise InvalidDropperDefinition(f'drop_full value "{rule["drop_full"]}" is not a bool!')
