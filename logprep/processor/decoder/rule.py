"""
Decoder
============

With the :code:`decoder` processor you are able to parse fields from
different formats.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given decoder rule

    filter: message
    decoder:
        source_format: json
        mapping:
            message: parsed
    description: 'parse message field to the field called parsed'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        "message": "{\\"timestamp\\": \\"2019-08-02T09:46:18.625Z\\", \\"log\\": \\"user login failed\\"}"
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "message": "{\\"timestamp\\": \\"2019-08-02T09:46:18.625Z\\", \\"log\\": \\"user login failed\\"}",
        "parsed": {
            "timestamp": "2019-08-02T09:46:18.625Z",
            "log": "user login failed"
        }
    }


.. autoclass:: logprep.processor.decoder.rule.DecoderRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for decoder:
---------------------

.. datatemplate:import-module:: tests.unit.processor.decoder.test_decoder
   :template: testcase-renderer.tmpl

"""

import typing

from attrs import define, field, validators

from logprep.processor.decoder.decoders import DECODERS
from logprep.processor.field_manager.rule import FieldManagerRule

IMPLEMENTED_DECODERS = tuple(DECODERS.keys())


class DecoderRule(FieldManagerRule):
    """Rule for the decoder processor"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for DecoderRule"""

        source_fields: list = field(
            validator=(
                validators.max_len(1),
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ),
            factory=list,
        )
        """The field to decode as list with maximum one element. For multi field operations
           use :code:`mapping` instead.
        """
        source_format: str = field(
            validator=(validators.instance_of(str), validators.in_(IMPLEMENTED_DECODERS)),
            default="json",
        )
        """The source format in the source field. Defaults to :code:`json`
        Possible values are 
        :code:`json`,
        :code:`base64`,
        :code:`clf`,
        :code:`nginx`,
        :code:`syslog_rfc5424`,
        :code:`syslog_rfc3164`,
        :code:`syslog_rfc3164_local`,
        :code:`logfmt`,
        :code:`cri`,
        :code:`docker`,
        :code:`decolorize`
        """

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(DecoderRule.Config, self._config)

    @property
    def source_format(self) -> str:
        """Getter for rule config"""
        return self.config.source_format
