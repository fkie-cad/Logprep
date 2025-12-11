"""
Decoder
============

The `decoder` processor decodes or parses field values from the configured
:code:`source_format`. Following :code:`source_formats` are implemented:

* json
* base64


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

import base64
import binascii
import json
from typing import Callable

from logprep.processor.decoder.rule import DecoderRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import FieldValue, add_fields_to, pop_dotted_field_value

DECODERS = {
    "json": json.loads,
    "base64": lambda x: base64.b64decode(x).decode("utf-8"),
}


class Decoder(FieldManager):
    """A processor that decodes field values to target fields"""

    rule_class = DecoderRule

    def _apply_single_target_processing(
        self,
        event,
        rule,
        rule_args,
    ):
        decoder = DECODERS[rule.source_format]
        source_fields, target_field, _, merge_with_target, overwrite_target = rule_args
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        source_field_values = [list(filter(lambda x: x is not None, source_field_values))]
        if not source_field_values:
            return
        parsed_source_field_values = self._decode(event, rule, decoder, source_field_values)
        if not parsed_source_field_values:
            return
        args = (event, target_field, parsed_source_field_values)
        self._write_to_single_target(args, merge_with_target, overwrite_target, rule)

    def _apply_mapping(self, event, rule, rule_args):
        decoder = DECODERS[rule.source_format]
        source_fields, _, mapping, merge_with_target, overwrite_target = rule_args
        source_fields, targets = list(zip(*mapping.items()))
        source_field_values = self._get_field_values(event, mapping.keys())
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        if not any(source_field_values):
            return
        source_field_values, targets = self._filter_missing_fields(source_field_values, targets)
        parsed_source_field_values = self._decode(event, rule, decoder, source_field_values)
        if not parsed_source_field_values:
            return
        add_fields_to(
            event,
            dict(zip(targets, parsed_source_field_values)),
            rule,
            merge_with_target,
            overwrite_target,
        )
        if rule.delete_source_fields:
            for dotted_field in source_fields:
                pop_dotted_field_value(event, dotted_field)

    def _decode(
        self,
        event: dict[str, FieldValue],
        rule: DecoderRule,
        decoder: Callable[[str], FieldValue],
        source_field_values: list[str],
    ) -> FieldValue:
        try:
            return [decoder(value) for value in source_field_values]
        except (binascii.Error, json.decoder.JSONDecodeError) as error:
            add_fields_to(event, {"tags": rule.failure_tags}, merge_with_target=True)
            self.result.errors.append(error)
            return []
