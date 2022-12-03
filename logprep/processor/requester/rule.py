"""
Requester
=========


"""
import json
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
    if parameter not in ["hooks", "cookies", "method", "url", "files"]
]

URL_REGEX_PATTERN = r"(http|https):\/\/.+"


HTTP_METHODS = ["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"]


class RequesterRule(FieldManagerRule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for RequesterRule"""

        source_fields: list = field(factory=list, converter=sorted)
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
                validators.matches_re(rf"^({URL_REGEX_PATTERN})|({FIELD_PATTERN}.*)"),
            ]
        )
        """the url for the request. You can use dissect pattern language to add field values"""
        json: dict = field(validator=validators.instance_of(dict), factory=dict)
        """ (Optional) The json payload. Can be templated by using the pattern
        :code:`${the.dotted.field}` somewhere in the key or value all elements.
        """
        data: str = field(validator=validators.instance_of(str), default="")
        """ (Optional) The data payload. Can be templated by using the pattern
        :code:`${the.dotted.field}` somewhere in value"""
        params: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """ (Optional) The query parameters. Can be templated by using the pattern
        :code:`${the.dotted.field}` somewhere in the key or value all elements."""
        headers: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """ (Optional) The http headers."""
        auth: tuple = field(
            validator=[validators.instance_of(tuple)],
            converter=tuple,
            factory=tuple,
        )
        """ (Optional) The authentication tuple. Defined as list."""

        def __attrs_post_init__(self):
            url_fields = re.findall(FIELD_PATTERN, self.url)
            json_fields = re.findall(FIELD_PATTERN, json.dumps(self.json))
            data_fields = re.findall(FIELD_PATTERN, self.data)
            params_fields = re.findall(FIELD_PATTERN, json.dumps(self.params))
            self.source_fields = list({*url_fields, *json_fields, *data_fields, *params_fields})

    # pylint: disable=missing-docstring
    @property
    def kwargs(self):
        kwargs = {
            key: getattr(self._config, key)
            for key in [*REQUEST_CONFIG_KEYS, "url", "method"]
            if getattr(self._config, key)
        }
        return kwargs

    # pylint: enable=missing-docstring
