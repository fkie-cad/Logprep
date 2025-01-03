"""
Dissector
=========

The `dissector` is a processor that tokenizes incoming strings using defined patterns.
The behavior is based of the logstash dissect filter plugin and has the same advantage that
for the event processing no regular expressions are used.
Additionally, it can be used to convert datatypes of given fields.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - dissectorname:
        type: dissector
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.dissector.processor.Dissector.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.dissector.rule
"""

from typing import TYPE_CHECKING, Callable, List, Tuple

from logprep.processor.dissector.rule import DissectorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import add_fields_to, get_dotted_field_value

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule


class Dissector(FieldManager):
    """A processor that tokenizes field values to new fields and converts datatypes"""

    rule_class = DissectorRule

    def _apply_rules(self, event, rule):
        self._apply_mapping(event, rule)
        self._apply_convert_datatype(event, rule)

    def _apply_mapping(self, event, rule):
        action_mappings_sorted_by_position = sorted(
            self._get_mappings(event, rule), key=lambda x: x[5]
        )
        for action, *args, _ in action_mappings_sorted_by_position:
            action(*args)

    def _get_mappings(self, event, rule) -> List[Tuple[Callable, dict, dict, str, "Rule", int]]:
        current_field = None
        target_field_mapping = {}
        for rule_action in rule.actions:
            (
                source_field,
                delimiter,
                target_field,
                rule_action,
                separator,
                strip_char,
                position,
            ) = rule_action
            if current_field != source_field:
                current_field = source_field
                loop_content = get_dotted_field_value(event, current_field)
                if loop_content is None:
                    if rule.ignore_missing_fields:
                        continue
                    error = Exception(f"dissector: mapping field '{source_field}' does not exist")
                    self._handle_warning_error(event, rule, error)
            if delimiter is not None and loop_content is not None:
                content, _, loop_content = loop_content.partition(delimiter)
            else:
                content = loop_content
            if target_field.startswith("?"):
                target_field_mapping[target_field.lstrip("?")] = content
                target_field = content
                content = ""
            if target_field.startswith("&"):
                target_field = target_field_mapping.get(target_field.lstrip("&"))
            if strip_char:
                content = content.strip(strip_char)
            field = {target_field: content}
            yield rule_action, event, field, separator, rule, position

    def _apply_convert_datatype(self, event, rule):
        for target_field, converter in rule.convert_actions:
            try:
                target_value = converter(get_dotted_field_value(event, target_field))
                add_fields_to(event, {target_field: target_value}, rule, overwrite_target=True)
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
