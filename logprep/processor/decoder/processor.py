"""
Decoder
============

The `decoder` processor ...

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: decoder
        rules:
            - tests/testdata/rules/

.. autoclass:: logprep.processor.decoder.processor.Decoder.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.decoder.processor.Decoder.rule
"""
from attrs import define, field, validators

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.decoder.rule import DecoderRule


class Decoder(FieldManager):
    """A processor that ..."""

    rule_class = DecoderRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """ Config of ..."""
        ...

    def _apply_rules(self, event, rule):
        pass