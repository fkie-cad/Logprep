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

from attrs import define

from logprep.processor.decoder.rule import DecoderRule
from logprep.processor.field_manager.processor import FieldManager


class Decoder(FieldManager):
    """A processor that ..."""

    rule_class = DecoderRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config of ..."""

    def _apply_rules(self, event, rule):
        super()._apply_rules(event, rule)

    def _apply_single_target_processing(self, event, rule, rule_args):
        source_fields, target_field, _, merge_with_target, overwrite_target = rule_args
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        source_field_values = list(filter(lambda x: x is not None, source_field_values))
        if not source_field_values:
            return
        parsed_source_field_values = [self._decoder.decode(value) for value in source_field_values]
        args = (event, target_field, parsed_source_field_values)
        self._write_to_single_target(args, merge_with_target, overwrite_target, rule)
