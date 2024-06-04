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
from collections import namedtuple
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
        event, target_field, source_fields_values = args
        target_field_value = get_dotted_field_value(event, target_field)
        State = namedtuple(
            "State",
            ["overwrite", "extend", "single_source_element", "target_is_list", "target_is_none"],
        )
        state = State(
            overwrite=overwrite_target,
            extend=extend_target_list,
            single_source_element=len(source_fields_values) == 1,
            target_is_list=isinstance(target_field_value, list),
            target_is_none=target_field_value is None,
        )
        if state.single_source_element and not state.extend:
            source_fields_values = source_fields_values.pop()

        if (
            state.extend
            and state.overwrite
            and not state.single_source_element
            and not state.target_is_list
        ):
            add_and_overwrite(event, target_field, source_fields_values)
            return

        if (
            state.extend
            and not state.overwrite
            and not state.single_source_element
            and not state.target_is_list
            and state.target_is_none
        ):
            add_and_overwrite(event, target_field, source_fields_values)
            return

        if (
            state.extend
            and not state.overwrite
            and not state.single_source_element
            and not state.target_is_list
        ):
            source_fields_values = [target_field_value, *source_fields_values]
            add_and_overwrite(event, target_field, source_fields_values)
            return

        if (
            state.extend
            and not state.overwrite
            and not state.single_source_element
            and state.target_is_list
        ):
            lists, not_lists = self._separate_lists_form_other_types(source_fields_values)
            flattened_source_fields = self._get_flatten_list(lists, not_lists)
            source_fields_values = [*target_field_value, *flattened_source_fields]
            add_and_overwrite(event, target_field, source_fields_values)
            return

        if state.overwrite and state.extend:
            lists, not_lists = self._separate_lists_form_other_types(source_fields_values)
            flattened_source_fields = self._get_flatten_list(lists, not_lists)
            source_fields_values = [*flattened_source_fields]
            add_and_overwrite(event, target_field, source_fields_values)
            return

        success = add_field_to(
            event, target_field, source_fields_values, state.extend, state.overwrite
        )
        if not success:
            raise FieldExistsWarning(rule, event, [target_field])

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
    def _get_flatten_list(lists: List[List], not_lists: List[Any]) -> List:
        duplicates = []
        flatten_list = []
        for field_value in list(itertools.chain(*lists, not_lists)):
            if field_value not in duplicates:
                duplicates.append(field_value)
                flatten_list.append(field_value)
        return flatten_list

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
