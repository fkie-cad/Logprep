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
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.field_manager.processor.FieldManager.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.field_manager.rule
"""

from logprep.abc.processor import Processor
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import (
    add_fields_to,
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
            rule.merge_with_target,
            rule.overwrite_target,
        )
        if rule.mapping:
            self._apply_mapping(event, rule, rule_args)
        if rule.source_fields and rule.target_field:
            self._apply_single_target_processing(event, rule, rule_args)

    def _apply_single_target_processing(self, event, rule, rule_args):
        source_fields, target_field, _, merge_with_target, overwrite_target = rule_args
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        source_field_values = list(filter(lambda x: x is not None, source_field_values))
        if not source_field_values:
            return
        args = (event, target_field, source_field_values)
        self._write_to_single_target(args, merge_with_target, overwrite_target, rule)

    def _apply_mapping(self, event, rule, rule_args):
        source_fields, _, mapping, merge_with_target, overwrite_target = rule_args
        source_fields, targets = list(zip(*mapping.items()))
        source_field_values = self._get_field_values(event, mapping.keys())
        self._handle_missing_fields(event, rule, source_fields, source_field_values)
        if not any(source_field_values):
            return
        source_field_values, targets = self._filter_missing_fields(source_field_values, targets)
        add_fields_to(
            event,
            dict(zip(targets, source_field_values)),
            rule,
            merge_with_target,
            overwrite_target,
        )
        if rule.delete_source_fields:
            for dotted_field in source_fields:
                pop_dotted_field_value(event, dotted_field)

    def _write_to_single_target(self, args, merge_with_target, overwrite_target, rule):
        event, target_field, source_fields_values = args
        if len(source_fields_values) == 1 and not merge_with_target:
            source_fields_values = source_fields_values.pop()
        if not merge_with_target:
            field = {target_field: source_fields_values}
            add_fields_to(event, field, rule, merge_with_target, overwrite_target)
            return
        new_values = self._overwrite_from_source_values(source_fields_values)
        if all(isinstance(element, dict) for element in new_values):
            # merge a list of dicts into one dict
            new_values = {key: value for dict_ in new_values for key, value in dict_.items()}
        if overwrite_target:
            # source values are already included in new_values, add_fields_to also does not
            # allow overwrite_target=True and marge_with_target=True at the same time
            merge_with_target = False
        add_fields_to(event, {target_field: new_values}, rule, merge_with_target, overwrite_target)

    def _overwrite_from_source_values(self, source_fields_values):
        duplicates = []
        ordered_flatten_list = []
        flat_source_fields = self._get_flatten_source_fields(source_fields_values)
        for field_value in flat_source_fields:
            if field_value not in duplicates:
                duplicates.append(field_value)
                ordered_flatten_list.append(field_value)
        return ordered_flatten_list

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
        return Exception(f"{self.name}: missing source_fields: {missing_fields}")

    @staticmethod
    def _get_flatten_source_fields(source_fields_values):
        flat_source_fields = []
        for item in source_fields_values:
            if isinstance(item, list):
                flat_source_fields.extend(item)
            else:
                flat_source_fields.append(item)
        return flat_source_fields

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
