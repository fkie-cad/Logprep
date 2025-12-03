"""
Decoder
============

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given decoder rule

    filter: message
    decoder:
        ...
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    <INCOMMING_EVENT>

..  code-block:: json
    :linenos:
    :caption: Processed event

    <PROCESSED_EVENT>


.. autoclass:: logprep.processor.decoder.rule.DecoderRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for decoder:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.decoder.test_decoder
   :template: testcase-renderer.tmpl

"""

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule

implemented_decoders = ("json",)


class DecoderRule(FieldManagerRule):
    """..."""

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
            validator=(validators.instance_of(str), validators.in_(implemented_decoders)),
            default="json",
        )
