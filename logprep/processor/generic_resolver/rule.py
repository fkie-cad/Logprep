"""This module is used to resolve field values from documents via a list."""
from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class GenericResolverRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config:
        """RuleConfig for GenericResolver"""

        field_mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ]
        )
        resolve_list: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        resolve_from_file: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(["path", "pattern"]),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        append_to_list: bool = field(validator=validators.instance_of(bool), default=False)

    @property
    def field_mapping(self) -> dict:
        """Returns the field mapping"""
        return self._config.field_mapping

    @property
    def resolve_list(self) -> dict:
        """Returns the resolve list"""
        return self._config.resolve_list

    @property
    def resolve_from_file(self) -> dict:
        """Returns the resolve file"""
        return self._config.resolve_from_file

    @property
    def append_to_list(self) -> bool:
        """Returns if it should append to a list"""
        return self._config.append_to_list
