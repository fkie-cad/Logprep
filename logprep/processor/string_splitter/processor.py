"""
StringSplitter
==============

The `string_splitter` processor splits string by whitespace (default) or a given delimiter and
writes the resulting list to a target field.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: string_splitter
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.string_splitter.processor.StringSplitter.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.string_splitter.rule
"""

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.string_splitter.rule import StringSplitterRule
from logprep.util.helper import get_dotted_field_value


class StringSplitter(FieldManager):
    """A processor that splits strings"""

    rule_class = StringSplitterRule

    def _apply_rules(self, event: dict, rule: StringSplitterRule):
        source_field = rule.source_fields[0]
        source_field_content = get_dotted_field_value(event, source_field)
        self._handle_missing_fields(event, rule, rule.source_fields, [source_field_content])
        if not isinstance(source_field_content, str):
            raise ProcessingWarning(f"source_field '{source_field}' is not a string", rule, event)
        result = source_field_content.split(rule.delimiter)
        self._write_target_field(event, rule, result)
