"""This module is used to drop specified fields that match a dropper filter."""

from typing import List
import warnings
from attrs import define, field, validators

from logprep.processor.base.rule import Rule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DropperRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for DroperRule"""

        drop: list = field(validator=validators.instance_of(list))
        drop_full: bool = field(validator=validators.instance_of(bool), default=True)

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        if rule.get("dropper") is None:
            drop_fields = pop_dotted_field_value(rule, "drop")
            if drop_fields is not None:
                add_and_overwrite(rule, "dropper.drop", drop_fields)
                warnings.warn("drop is deprecated. Use dropper.drop instead", DeprecationWarning)
            drop_full = pop_dotted_field_value(rule, "drop_full")
            if drop_full is not None:
                add_and_overwrite(rule, "dropper.drop_full", drop_full)
                warnings.warn(
                    "drop_full is deprecated. Use dropper.drop_full instead", DeprecationWarning
                )

    @property
    def fields_to_drop(self) -> List[str]:
        """Returns fields_to_drop"""
        return self._config.drop

    @property
    def drop_full(self) -> bool:
        """Returns drop_full"""
        return self._config.drop_full
