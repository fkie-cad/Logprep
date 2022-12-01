"""
Requester
============

"""
import inspect
import requests
from attrs import define, field, validators
from logprep.processor.field_manager.rule import FieldManagerRule

parameter_keys = inspect.signature(requests.Request).parameters.keys()
REQUEST_CONFIG_KEYS = [
    parameter for parameter in parameter_keys if parameter not in ["hooks", "cookies"]
]


class RequesterRule(FieldManagerRule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for RequesterRule"""

        source_fields: list = field(factory=list)
        target_field: str = field(factory=str)
        kwargs: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(REQUEST_CONFIG_KEYS),
                    value_validator=validators.instance_of(object),
                ),
            ]
        )
