"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The Requester is configured by the keyword :code:`requester`.
It can be used to trigger external systems via web request or enrich eventdata by external
apis.

A speaking example for event enrichment via external api:

..  code-block:: yaml
    :linenos:
    :caption: Given requester rule

    filter: 'domain'
    requester:
      url: https://internal.cmdb.local/api/v1/locations
      method: POST
      target_field: cmdb.location
      headers:
        Authorization: Bearer askdfjpiowejf283u9r
      json:
        hostname: ${message.hostname}
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"message": {"hostname": "BB37293hhj"}}

..  code-block:: json
    :linenos:
    :caption: Raw response json data given from the api

    {
        "city": "Montreal",
        "Building": "L76",
        "Floor": 3,
        "Room": 34
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {"message": {"hostname": "BB37293hhj"},
     "cmdb": {
         "location": {
             "city": "Montreal",
             "Building": "L76",
             "Floor": 3,
             "Room": 34
             }
        }
    }

.. autoclass:: logprep.processor.requester.rule.RequesterRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import inspect
import json
import re

import requests
from attrs import define, field, validators

from logprep.processor.field_manager.rule import FIELD_PATTERN, FieldManagerRule

parameter_keys = inspect.signature(requests.Request).parameters.keys()
REQUEST_CONFIG_KEYS = [
    parameter for parameter in parameter_keys if parameter not in ["hooks", "cookies", "files"]
] + ["timeout", "proxies", "verify", "cert"]
URL_REGEX_PATTERN = r"(http|https):\/\/.+"
HTTP_METHODS = ["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"]


class RequesterRule(FieldManagerRule):
    """RequesterRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for RequesterRule"""

        source_fields: list = field(
            factory=list, converter=sorted, validator=validators.instance_of(list)
        )
        target_field: str = field(factory=str, validator=validators.instance_of(str))
        """(Optional) The target field to write the complete response json or body to"""
        target_field_mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """(Optional) A mapping from dotted_fields to dotted_fields to extract data from response
        json to target fields. If target_field is given too, this is made additionally"""
        method: str = field(
            validator=[
                validators.instance_of(str),
                validators.in_(HTTP_METHODS),
            ]
        )
        """The method for the request. must be one of
        :code:`GET`, :code:`OPTIONS`, :code:`HEAD`,
        :code:`POST`, :code:`PUT`, :code:`PATCH`, :code:`DELETE`"""
        url: str = field(
            validator=[
                validators.instance_of(str),
                validators.matches_re(rf"^({URL_REGEX_PATTERN})|({FIELD_PATTERN}.*)"),
            ]
        )
        """The url for the request. You can use dissect pattern language to add field values"""
        json: dict = field(validator=validators.instance_of(dict), factory=dict)
        """ (Optional) The json payload. Can be enriched with event data by using the pattern
        :code:`${the.dotted.field}` to retrieve nested field values.
        """
        data: str = field(validator=validators.instance_of(str), default="")
        """ (Optional) The data payload. Can be enriched with event data by using the pattern
        :code:`${the.dotted.field}` to retrieve nested field values."""
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
        """ (Optional) The query parameters as dictionary. Can be enriched with event data by
        using the pattern :code:`${the.dotted.field}` to retrieve nested field values."""
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
        """ (Optional) The http headers as dictionary."""
        auth: tuple = field(
            validator=[validators.instance_of(tuple)],
            converter=tuple,
            factory=tuple,
        )
        """ (Optional) The authentication tuple. Defined as list. Will be converted to tuple"""
        timeout: float = field(validator=validators.instance_of(float), converter=float, default=2)
        """ (Optional) The timeout in seconds as float for the request. Defaults to 2 seconds"""
        verify: bool = field(validator=validators.instance_of(bool), default=True)
        """ (Optional) Whether or not verify the ssl context. Defaults to :code:`True`."""
        proxies: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """(Optional) Dictionary mapping protocol or protocol and host to the
        URL of the proxy (e.g. :code:`{"http": "foo.bar:3128", "http://host.name": "foo.bar:4012"}`)
        to be used on the request"""
        cert: str = field(validator=validators.instance_of(str), default="")
        """(Optional) SSL client certificate as path to ssl client cert file (.pem)."""
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

        def __attrs_post_init__(self):
            url_fields = re.findall(FIELD_PATTERN, self.url)
            json_fields = re.findall(FIELD_PATTERN, json.dumps(self.json))
            data_fields = re.findall(FIELD_PATTERN, self.data)
            params_fields = re.findall(FIELD_PATTERN, json.dumps(self.params))
            self.source_fields = list({*url_fields, *json_fields, *data_fields, *params_fields})
            super().__attrs_post_init__()

    # pylint: disable=missing-docstring
    @property
    def kwargs(self):
        kwargs = {
            key: getattr(self._config, key)
            for key in REQUEST_CONFIG_KEYS
            if getattr(self._config, key)
        }
        return kwargs

    @property
    def target_field_mapping(self):
        return self._config.target_field_mapping

    # pylint: enable=missing-docstring
