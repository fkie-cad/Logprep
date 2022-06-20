"""This module is used to delete full events matching a given filter."""

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class DeleteRuleError(InvalidRuleDefinitionError):
    """Base class for Delete rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"Delete rule ({message}): ")


class InvalidDeleteDefinition(DeleteRuleError):
    """Raise if Delete definition invalid."""

    def __init__(self, definition):
        message = f"The following Delete definition is invalid: {definition}"
        super().__init__(message)


class DeleteRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, delete: bool):
        super().__init__(filter_rule)
        self._delete_or_not = delete

    def __eq__(self, other: "DeleteRule") -> bool:
        return (other.filter == self._filter) and (self._delete_or_not == other.delete_or_not)

    # pylint: disable=C0111
    @property
    def delete_or_not(self) -> bool:
        return self._delete_or_not

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "DeleteRule":
        DeleteRule._check_rule_validity(rule, "delete")
        DeleteRule._check_if_delete_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return DeleteRule(filter_expression, rule["delete"])

    @staticmethod
    def _check_if_delete_valid(rule: dict):
        if not isinstance(rule["delete"], bool):
            raise InvalidDeleteDefinition(f'Delete value "{rule["delete"]}" is not a boolean!')
