"""
FieldManager
=========

The `dissector` is a processor that tokenizes incoming strings using defined patterns.
The behavior is based of the logstash dissect filter plugin and has the same advantage that
for the event processing no regular expressions are used.
Additionally it can be used to convert datatypes of given fields.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - fieldmanagername:
        type: field_manager
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from typing import List
from logprep.abc import Processor
from logprep.processor.base.rule import FieldManagerRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite
from logprep.processor.base.exceptions import DuplicationError


class FieldManager(Processor):
    """A processor that copies, moves or merges source fields to one target field"""

    rule_class = FieldManagerRule

    def _apply_rules(self, event, rule):
        field_values = [
            get_dotted_field_value(event, source_field) for source_field in rule.source_fields
        ]
        if None in field_values:
            missing_fields = [
                rule.source_fields[index]
                for value, index in enumerate(field_values)
                if value is None
            ]
            error = BaseException(f"{self.name}: missing source_fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)

        if len(field_values) == 1 and not rule.extend_target_list:
            field_values = field_values.pop()
        extend_target_list = rule.extend_target_list
        overwrite_target = rule.overwrite_target
        if extend_target_list and overwrite_target:
            field_values_lists = list(filter(lambda x: isinstance(x, list), field_values))
            field_values_not_list = list(filter(lambda x: not isinstance(x, list), field_values))
            target_field_value = self._get_deduplicated_sorted_flatten_list(
                field_values_lists, field_values_not_list
            )
            add_and_overwrite(event, rule.target_field, target_field_value)
        if extend_target_list and not overwrite_target:
            target_field_value = get_dotted_field_value(event, rule.target_field)
            field_values_lists = list(filter(lambda x: isinstance(x, list), field_values))
            field_values_not_list = list(filter(lambda x: not isinstance(x, list), field_values))
            if isinstance(target_field_value, list):
                target_field_value = self._get_deduplicated_sorted_flatten_list(
                    field_values_lists, [*target_field_value, *field_values_not_list]
                )
            else:
                target_field_value = field_values
            add_and_overwrite(event, rule.target_field, target_field_value)
        if not extend_target_list and overwrite_target:
            add_and_overwrite(event, rule.target_field, field_values)
        if not extend_target_list and not overwrite_target:
            successfull = add_field_to(
                event,
                rule.target_field,
                field_values,
                extends_lists=extend_target_list,
                overwrite_output_field=overwrite_target,
            )
            if not successfull:
                raise DuplicationError(self.name, [rule.target_field])

    @staticmethod
    def _get_deduplicated_sorted_flatten_list(lists: List[List], not_lists: List[any]) -> list:
        return sorted(list({*sum(lists, []), *not_lists}))
