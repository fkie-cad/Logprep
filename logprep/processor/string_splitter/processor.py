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
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.string_splitter.processor.StringSplitter.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.string_splitter.rule
"""

from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.string_splitter.rule import StringSplitterRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class StringSplitter(FieldManager):
    """A processor that splits strings"""

    rule_class = StringSplitterRule

    def _apply_rules(self, event: dict, rule: StringSplitterRule):
        target_field = rule.target_field
        source_field = rule.source_fields[0]
        source_field_content = get_dotted_field_value(event, source_field)
        if not isinstance(source_field_content, str):
            raise ProcessingWarning(f"source_field '{source_field}' is not a string", rule, event)
        result = source_field_content.split(rule.delimeter)
        successful = add_field_to(
            event=event,
            output_field=target_field,
            content=result,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
        if not successful:
            raise FieldExistsWarning(rule, event, [target_field])
