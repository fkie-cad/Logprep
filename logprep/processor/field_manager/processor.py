"""
FieldManager
============

The `field_manager` processor copies or moves values from multiple source fields to one
target field.
Additionally, it can be used to merge multiple source field values into one target field value.
In this process, source field lists will be merged.


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
from typing import List, Tuple, Any

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite


class FieldManager(Processor):
    """A processor that copies, moves or merges source fields to one target field"""

    rule_class = FieldManagerRule

    def _apply_rules(self, event, rule):
        source_fields = rule.source_fields
        target_field = rule.target_field
        field_values = self._get_field_values(event, rule)
        self._check_for_missing_fields(event, rule, source_fields, field_values)
        extend_target_list = rule.extend_target_list
        overwrite_target = rule.overwrite_target
        args = (event, target_field, field_values)
        if extend_target_list and overwrite_target:
            self._overwrite_with_list_from_source_field_values(*args)
        if extend_target_list and not overwrite_target:
            self._overwrite_with_list_from_source_field_values_include_target_field_value(*args)
        if not extend_target_list and overwrite_target:
            self._overwrite_target_with_source_field_values(*args)
        if not extend_target_list and not overwrite_target:
            self._add_field_to(*args)

    def _add_field_to(self, *args):
        event, target_field, field_values = args
        if len(field_values) == 1:
            field_values = field_values.pop()
        successful = add_field_to(event, target_field, field_values, False, False)
        if not successful:
            raise DuplicationError(self.name, [target_field])

    def _overwrite_target_with_source_field_values(self, event, target_field, field_values):
        if len(field_values) == 1:
            field_values = field_values.pop()
        add_and_overwrite(event, target_field, field_values)

    def _overwrite_with_list_from_source_field_values_include_target_field_value(self, *args):
        event, target_field, field_values = args
        origin_field_value = get_dotted_field_value(event, target_field)
        if origin_field_value is not None:
            field_values.append(origin_field_value)
        self._overwrite_with_list_from_source_field_values(event, target_field, field_values)

    def _overwrite_with_list_from_source_field_values(self, *args):
        event, target_field, field_values = args
        lists, other = self._separate_lists_form_other_types(field_values)
        target_field_value = self._get_deduplicated_sorted_flatten_list(lists, other)
        add_and_overwrite(event, target_field, target_field_value)

    def _check_for_missing_fields(self, event, rule, source_fields, field_values):
        if None in field_values:
            error = self._get_missing_fields_error(source_fields, field_values)
            self._handle_warning_error(event, rule, error)

    def _get_field_values(self, event, rule):
        return [get_dotted_field_value(event, source_field) for source_field in rule.source_fields]

    def _get_missing_fields_error(self, source_fields, field_values):
        missing_fields = [key for key, value in zip(source_fields, field_values) if value is None]
        error = BaseException(f"{self.name}: missing source_fields: {missing_fields}")
        return error

    @staticmethod
    def _separate_lists_form_other_types(field_values: List[Any]) -> Tuple[List[List], List[Any]]:
        field_values_lists = list(filter(lambda x: isinstance(x, list), field_values))
        field_values_not_list = list(filter(lambda x: not isinstance(x, list), field_values))
        return field_values_lists, field_values_not_list

    @staticmethod
    def _get_deduplicated_sorted_flatten_list(lists: List[List], not_lists: List[Any]) -> List:
        return sorted(list({*sum(lists, []), *not_lists}))
