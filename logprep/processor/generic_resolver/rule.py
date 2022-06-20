"""This module is used to resolve field values from documents via a list."""

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class GenericResolverRuleError(InvalidRuleDefinitionError):
    """Base class for GenericResolver rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GenericResolver rule ({message}): ")


class InvalidGenericResolverDefinition(GenericResolverRuleError):
    """Raise if GenericResolver definition invalid."""

    def __init__(self, definition):
        message = f"The following GenericResolver definition is invalid: {definition}"
        super().__init__(message)


class GenericResolverRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, generic_resolver_cfg: dict):
        super().__init__(filter_rule)

        self._field_mapping = generic_resolver_cfg["field_mapping"]
        self._resolve_list = generic_resolver_cfg.get("resolve_list", {})
        self._resolve_from_file = generic_resolver_cfg.get("resolve_from_file", {})
        self._append_to_list = generic_resolver_cfg.get("append_to_list", False)

    def __eq__(self, other: "GenericResolverRule") -> bool:
        return (
            (other.filter == self._filter)
            and (self._field_mapping == other.field_mapping)
            and (self._resolve_list == other.resolve_list)
            and (self._append_to_list == other.append_to_list)
        )

    # pylint: disable=C0111
    @property
    def field_mapping(self) -> dict:
        return self._field_mapping

    @property
    def resolve_list(self) -> dict:
        return self._resolve_list

    @property
    def resolve_from_file(self) -> dict:
        return self._resolve_from_file

    @property
    def append_to_list(self) -> bool:
        return self._append_to_list

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "GenericResolverRule":
        GenericResolverRule._check_rule_validity(rule, "generic_resolver")
        GenericResolverRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return GenericResolverRule(filter_expression, rule["generic_resolver"])

    @staticmethod
    def _check_if_valid(rule: dict):
        generic_resolver_cfg = rule["generic_resolver"]
        for field in ("field_mapping",):
            if not isinstance(generic_resolver_cfg[field], dict):
                raise InvalidGenericResolverDefinition(
                    f'"{field}" value "{generic_resolver_cfg[field]}" is not a string!'
                )
