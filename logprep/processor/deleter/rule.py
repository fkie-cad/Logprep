"""This module is used to delete full events matching a given filter."""
import warnings
from attrs import define, field, validators
from logprep.processor.base.rule import Rule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DeleterRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for DeleterRule"""

        delete: bool = field(validator=validators.instance_of(bool))

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        if rule.get("deleter") is None:
            deleter_config = pop_dotted_field_value(rule, "delete")
        if deleter_config is not None:
            add_and_overwrite(rule, "deleter.delete", deleter_config)
            warnings.warn(
                ("delete is deprecated. " "Use deleter.delete instead"),
                DeprecationWarning,
            )

    @property
    def delete_event(self) -> bool:
        """Returns delete_or_not"""
        return self._config.delete
