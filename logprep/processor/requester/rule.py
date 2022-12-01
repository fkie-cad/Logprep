"""
Requester
============

"""
from functools import partial
from attrs import define, field, validators
from logprep.util.validators import min_len_validator
from logprep.processor.field_manager.rule import FieldManagerRule


class RequesterRule(FieldManagerRule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for RequesterRule"""

        source_fields: list = field(factory=list)
        target_field: str = field(factory=str)
        kwargs: dict = field(validator=[validators.instance_of(dict)])
