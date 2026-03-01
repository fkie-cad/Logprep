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

from collections.abc import Callable, Generator

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.rule import Rule
from logprep.processor.dissector.rule import DissectorRule
from logprep.util.helper import (
    MISSING,
    FieldValue,
    add_fields_to,
    get_dotted_field_value,
    get_dotted_field_value_with_explicit_missing,
)


class Dissector(FieldManager):
    """A processor that tokenizes field values to new fields and converts datatypes"""

    rule_class = DissectorRule  # type: ignore

    def _apply_rules(self, event, rule):
        self.__apply_mapping(event, rule)
        self._apply_convert_datatype(event, rule)

    def __apply_mapping(self, event, rule):
        action_mappings_sorted_by_position = sorted(
            self._get_mappings(event, rule), key=lambda x: x[5]
        )
        for action, *args, _ in action_mappings_sorted_by_position:
            action(*args)

    def _get_mappings(
        self, event: dict[str, FieldValue], rule: DissectorRule
    ) -> Generator[tuple[Callable, dict, dict, str, Rule, int]]:
        target_field_mapping = {}
        for source_field, actions in rule.actions_by_source_field.items():

            value = get_dotted_field_value_with_explicit_missing(event, source_field)
            if value is MISSING:
                if rule.ignore_missing_fields:
                    continue
                error = Exception(f"dissector: mapping field '{source_field}' does not exist")
                self._handle_warning_error(event, rule, error)
                continue
            if not isinstance(value, str):
                error = ValueError(f"dissector: encountered non-string value type {type(value)}")
                self._handle_warning_error(event, rule, error)
                continue

            remaining_value = value
            for action in actions:
                if action.delimiter is not None:
                    content, _, remaining_value = remaining_value.partition(action.delimiter)
                else:
                    content = remaining_value

                target_field = action.target_field
                if target_field.startswith("?"):
                    target_field_mapping[target_field.lstrip("?")] = content
                    target_field = content
                    content = ""
                if target_field.startswith("&"):
                    try:
                        target_field = target_field_mapping[target_field.lstrip("&")]
                    except KeyError:
                        self._handle_warning_error(
                            event,
                            rule,
                            Exception(f"field reference ({target_field}) before declaration (?)"),
                        )
                        break
                if action.strip_char and content is not None:
                    content = content.strip(action.strip_char)
                field = {target_field: content}
                yield action.action, event, field, action.separator, rule, action.position

    def _apply_convert_datatype(self, event: dict[str, FieldValue], rule: DissectorRule):
        for target_field, converter in rule.convert_actions:
            try:
                target_value = converter(get_dotted_field_value(event, target_field))
                add_fields_to(event, {target_field: target_value}, rule, overwrite_target=True)
            except ValueError as error:
                self._handle_warning_error(event, rule, error)
