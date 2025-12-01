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

from attrs import define

from logprep.processor.field_manager.rule import FieldManagerRule


class DecoderRule(FieldManagerRule):
    """..."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for DecoderRule"""
