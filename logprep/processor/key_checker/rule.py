"""
KeyCheckerRule
------------

The `key_checker` processor needs a list with atleast one element in it.

"""
from functools import partial

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.base.rule import Rule


from logprep.util.validators import min_len_validator


class KeyCheckerRule(Rule):
    """key_checker rule"""

    @define(kw_only=True)
    class Config:
        """key_checker rule config"""

        key_list: list = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.instance_of(list),
                ),
                partial(min_len_validator, min_length=1),
            ]
        )

        error_field: str = field(validator=validators.instance_of(str))

    def __eq__(self, other: "KeyCheckerRule") -> bool:
        return all([other.filter == self._filter, other._config == self._config])

    def __init__(self, filter_rule: FilterExpression, config: "KeyCheckerRule.Config"):
        super().__init__(filter_rule)
        self._config = config

    @property
    def key_list(self) -> list:  # pylint: disable=missing-docstring
        return self._config.key_list

    @property
    def error_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.error_field

    @staticmethod
    def _create_from_dict(rule: dict) -> "KeyCheckerRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("key_checker")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = KeyCheckerRule.Config(**config)
        return KeyCheckerRule(filter_expression, config)
