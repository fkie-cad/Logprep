"""
FieldManager
============

The `field_manager` processor copies or moves values from multiple source fields to one
target field.
Additionally, it can be used to merge multiple source field values into one target field value.
In this process, source field lists will be merged.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - fieldmanagername:
        type: field_manager
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.field_manager.processor.FieldManager.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.field_manager.rule
"""
import itertools
from typing import Any, List, Tuple

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import (
    add_and_overwrite,
    add_field_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)


class FieldManager(Processor):
    """A processor that copies, moves or merges source fields to one target field"""

    rule_class = FieldManagerRule

    def _apply_rules(self, event, rule):
        rule_args = (
            rule.source_fields,
            rule.target_field,
            rule.mapping,
            rule.extend_target_list,
            rule.overwrite_target,
        )
        if rule.mapping:
            self._apply_mapping(event, rule, rule_args)
        if rule.source_fields and rule.target_field:
            self._apply_single_target_processing(event, rule, rule_args)

    def _apply_single_target_processing(self, event, rule, rule_args):
        source_fields, target_field, _, extend_target_list, overwrite_target = rule_args
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        source_field_values = list(filter(lambda x: x is not None, source_field_values))
        if not source_field_values:
            return
        args = (event, target_field, source_field_values)
        self._write_to_single_target(args, extend_target_list, overwrite_target, rule)

    def _apply_mapping(self, event, rule, rule_args):
        source_fields, _, mapping, _, _ = rule_args
        source_fields, targets = list(zip(*mapping.items()))
        source_field_values = self._get_field_values(event, mapping.keys())
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        if not any(source_field_values):
            return
        source_field_values, targets = self._filter_missing_fields(source_field_values, targets)
        self._write_to_multiple_targets(event, targets, source_field_values, rule, rule_args)
        if rule.delete_source_fields:
            for dotted_field in source_fields:
                pop_dotted_field_value(event, dotted_field)

    def _write_to_multiple_targets(self, event, target_fields, field_values, rule, rule_args):
        _, _, _, extend_target_list, overwrite_target = rule_args
        results = map(
            add_field_to,
            itertools.repeat(event, len(target_fields)),
            target_fields,
            field_values,
            itertools.repeat(extend_target_list, len(target_fields)),
            itertools.repeat(overwrite_target, len(target_fields)),
        )
        if not all(results):
            unsuccessful_indices = [i for i, x in enumerate(results) if not x]
            unsuccessful_targets = [
                x for i, x in enumerate(target_fields) if i in unsuccessful_indices
            ]
            raise FieldExistsWarning(rule, event, unsuccessful_targets)

    def _write_to_single_target(self, args, extend_target_list, overwrite_target, rule):
        if extend_target_list and overwrite_target:
            self._overwrite_with_list_from_source_field_values(*args)
        if extend_target_list and not overwrite_target:
            self._overwrite_with_list_from_source_field_values_include_target_field_value(*args)
        if not extend_target_list and overwrite_target:
            self._overwrite_target_with_source_field_values(*args)
        if not extend_target_list and not overwrite_target:
            self._add_field_to(*args, rule=rule)

    def _add_field_to(self, *args, rule):
        event, target_field, field_values = args
        if len(field_values) == 1:
            field_values = field_values.pop()
        successful = add_field_to(event, target_field, field_values, False, False)
        if not successful:
            raise FieldExistsWarning(rule, event, [target_field])

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

    def _handle_missing_fields(self, event, rule, source_fields, field_values):
        if rule.ignore_missing_fields:
            return False
        if None in field_values:
            error = self._get_missing_fields_error(source_fields, field_values)
            self._handle_warning_error(
                event,
                rule,
                error,
                failure_tags=[f"_{self.rule_class.rule_type}_missing_field_warning"],
            )
            return True
        return False

    @staticmethod
    def _get_field_values(event, source):
        return [get_dotted_field_value(event, source_field) for source_field in source]

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

    @staticmethod
    def _filter_missing_fields(source_field_values, targets):
        if None in source_field_values:
            mapping = [
                (value, targets[i])
                for i, value in enumerate(source_field_values)
                if value is not None
            ]
            return list(zip(*mapping))
        return source_field_values, targets
