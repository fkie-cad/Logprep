"""
StringSplitter
============

The `string_splitter` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: string_splitter
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.string_splitter.rule import StringSplitterRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class StringSplitter(FieldManager):
    """A processor that ..."""

    rule_class = StringSplitterRule

    def _apply_rules(self, event: dict, rule: StringSplitterRule):
        source_field_content = get_dotted_field_value(event, rule.source_fields[0])
        result = source_field_content.split(rule.delimeter)
        successfull = add_field_to(
            event=event,
            output_field=rule.target_field,
            content=result,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
