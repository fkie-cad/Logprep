"""This module is used to delete full events matching a given filter."""
from attrs import define, field, validators
from logprep.processor.base.rule import Rule


class DeleterRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config:
        """Config for DeleterRule"""

        delete: bool = field(validator=validators.instance_of(bool))

    @classmethod
    def _create_from_dict(cls, rule: dict) -> "DeleterRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = cls.Config(delete=rule.get("delete"))
        return cls(filter_expression, config)

    # pylint: disable=C0111
    @property
    def delete_or_not(self) -> bool:
        """Returns delete_or_not"""
        return self._config.delete
