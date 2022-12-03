"""
Requester
=========


"""
import re
import inspect
import requests
from attrs import define, field, validators
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.processor.calculator.rule import FIELD_PATTERN

parameter_keys = inspect.signature(requests.Request).parameters.keys()
REQUEST_CONFIG_KEYS = [
    parameter
    for parameter in parameter_keys
    if parameter not in ["hooks", "cookies", "method", "url"]
]

URL_REGEX_PATTERN = r"(http|https):\/\/.+"


HTTP_METHODS = ["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"]


class RequesterRule(FieldManagerRule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for RequesterRule"""

        source_fields: list = field(factory=list)
        target_field: str = field(factory=str)
        method: str = field(
            validator=[
                validators.instance_of(str),
                validators.in_(HTTP_METHODS),
            ]
        )
        """the method for the request. must be one of
        :code:`GET`, :code:`OPTIONS`, :code:`HEAD`,
        :code:`POST`, :code:`PUT`, :code:`PATCH`, :code:`DELETE`"""
        url: str = field(
            validator=[
                validators.instance_of(str),
            ]
        )
        """the url for the request. You can use dissect pattern language to add field values"""
        kwargs: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(REQUEST_CONFIG_KEYS),
                    value_validator=validators.instance_of(object),
                ),
            ],
            factory=dict,
        )
        """keyword arguments for the request. You can use dissect pattern language to
        fill with field values. Valid kwargs are:
        :code:`headers`, :code:`files`, :code:`data`, :code:`params`, :code:`auth`, :code:`json`"""

        def __attrs_post_init__(self):
            url_fields = re.findall(FIELD_PATTERN, self.url)
            self.source_fields = list({*url_fields})

    @property
    def url(self):
        return self._config.url

    @property
    def method(self):
        return self._config.method

    @property
    def kwargs(self):
        return self._config.kwargs
