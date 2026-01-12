"""
Decoder
============

The `decoder` processor decodes or parses field values from the configured
:code:`source_format`. Following options for :code:`source_format` are implemented:

* json
* base64
* clf, see: https://en.wikipedia.org/wiki/Common_Log_Format
* nginx parser for kubernetes ingress
* syslog_rfc3164
* syslog_rfc3164_local
* syslog_rfc5324
* logfmt
* cri
* docker
* decolorize (removing color codes in logs)


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

.. automodule:: logprep.processor.decoder.rule
"""

import typing
from typing import Callable

from typing_extensions import override

from logprep.processor.decoder.decoders import DECODERS, DecoderError
from logprep.processor.decoder.rule import DecoderRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import FieldValue, add_fields_to
from logprep.util.typing import is_list_of


class Decoder(FieldManager):
    """A processor that decodes field values to target fields"""

    rule_class = DecoderRule

    @override
    def transform_values(
        self,
        source_field_values: list[FieldValue],
        event: dict[str, FieldValue],
        rule: FieldManagerRule,
    ) -> list[FieldValue]:
        decoder_rule = typing.cast(DecoderRule, rule)
        decoder = DECODERS[decoder_rule.source_format]
        return self._decode(event, decoder_rule, decoder, source_field_values)

    def _decode(
        self,
        event: dict[str, FieldValue],
        rule: DecoderRule,
        decoder: Callable[[str], FieldValue],
        source_field_values: list[FieldValue],
    ) -> list[FieldValue]:
        try:
            if is_list_of(source_field_values, str):
                return [decoder(value) for value in source_field_values]
            raise DecoderError("can only decode string values")
        except DecoderError as error:
            add_fields_to(event, {"tags": rule.failure_tags}, merge_with_target=True)
            self.result.errors.append(error)
            return []
