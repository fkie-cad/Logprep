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
from logprep.util.helper import FieldValue, add_fields_to

DECODERS = {
    "json": json.loads,
    "base64": lambda x: base64.b64decode(x).decode("utf-8"),
}


class Decoder(FieldManager):
    """A processor that decodes field values to target fields"""

    rule_class = DecoderRule

    def transform_values(
        self, source_field_values: list[FieldValue], event: dict[str, FieldValue], rule: DecoderRule
    ) -> list[FieldValue]:
        decoder = DECODERS[rule.source_format]
        return self._decode(event, rule, decoder, source_field_values)

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
