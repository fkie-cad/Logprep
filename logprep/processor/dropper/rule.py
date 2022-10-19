"""This module is used to drop specified fields that match a dropper filter."""

from typing import List
from attrs import define, field, validators

from logprep.processor.base.rule import Rule
from logprep.processor.base.exceptions import InvalidRuleDefinitionError


class DropperRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config:
        """RuleConfig for Concatenator"""

        fields_to_drop: list = field(validator=validators.instance_of(list))
        drop_full: bool = field(validator=validators.instance_of(bool), default=True)

    @classmethod
    def _create_from_dict(cls, rule: dict) -> "Rule":
        filter_expression = Rule._create_filter_expression(rule)
        drop_fields = rule.get("drop")
        drop_full = rule.get("drop_full")
        drop_full = drop_full if drop_full is not None else True
        if drop_fields is None:
            raise InvalidRuleDefinitionError("config not under key drop")
        if not isinstance(drop_fields, list):
            raise InvalidRuleDefinitionError("config is not a list")
        config = cls.Config(fields_to_drop=drop_fields, drop_full=drop_full)
        return cls(filter_expression, config)

    @property
    def fields_to_drop(self) -> List[str]:
        """Returns fields_to_drop"""
        return self._config.fields_to_drop

    @property
    def drop_full(self) -> bool:
        """Returns drop_full"""
        return self._config.drop_full
