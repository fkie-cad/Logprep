"""
|PROCESSOR_NAME|
================

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
    FieldValue,
    add_fields_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)


class FieldManager(Processor):
    """A processor that copies, moves or merges source fields to one target field"""

    rule_class = FieldManagerRule

    def _apply_rules(self, event: dict[str, FieldValue], rule: FieldManagerRule) -> None:
        config = rule.config

        if config.mapping:
            self.__apply_mapping(event, rule, config)
        if config.source_fields and config.target_field:
            self._apply_single_target_processing(event, rule, config)

    def _apply_single_target_processing(
        self, event: dict, rule: FieldManagerRule, config: FieldManagerRule.Config
    ) -> None:
        source_field_values: list[FieldValue] = self._get_field_values(event, config.source_fields)
        self._handle_missing_fields(
            event, rule, config.source_fields, source_field_values, config=config
        )
        source_field_values = [value for value in source_field_values if value is not None]
        # TODO: This is problematic as source_fields with only 0, False, "" or [] are treated as falsy,
        # meaning especially 0, and False only source fields cannot be copied in this way, this seems
        # to be a large oversight, and should be fixed, right now its not fixed as the decoder,
        # actually needs this behaviour atleast for ""
        if not source_field_values:
            return
        target_field_values = self.transform_values(source_field_values, event, rule)
        if not target_field_values:
            return

        self._write_to_single_target(event, rule, config, target_field_values)

    def __apply_mapping(
        self, event: dict, rule: FieldManagerRule, config: FieldManagerRule.Config
    ) -> None:
        mapping = config.mapping
        source_fields = list(mapping.keys())
        source_field_values = self._get_field_values(event, source_fields)

        self._handle_missing_fields(event, rule, source_fields, source_field_values, config=config)

        if not source_field_values:
            return

        targets = list(mapping.values())
        source_field_values, targets = self._filter_missing_fields(source_field_values, targets)
        target_field_values = self.transform_values(source_field_values, event, rule)
        if not target_field_values:
            return

        add_fields_to(
            event,
            dict(zip(targets, target_field_values)),
            rule,
            config.merge_with_target,
            config.overwrite_target,
        )
        if config.delete_source_fields:
            for dotted_field in source_fields:
                pop_dotted_field_value(event, dotted_field)

    def _write_to_single_target(
        self,
        event: dict,
        rule: FieldManagerRule,
        config: FieldManagerRule.Config,
        target_field_values: list[FieldValue],
    ) -> None:
        if not config.merge_with_target:
            value = target_field_values[0] if len(target_field_values) == 1 else target_field_values

            add_fields_to(
                event,
                {config.target_field: value},
                rule,
                merge_with_target=False,
                overwrite_target=config.overwrite_target,
            )
            return

        new_values: list[FieldValue] = self._flatten_values(target_field_values, config.deduplicate)
        if all(isinstance(element, dict) for element in new_values):
            merged_values: dict[str, FieldValue] = {}
            for value in new_values:
                assert isinstance(value, dict)
                merged_values.update(value)
            result: FieldValue = merged_values
        else:
            result = new_values

        add_fields_to(
            event,
            {config.target_field: result},
            rule,
            merge_with_target=not config.overwrite_target,
            overwrite_target=config.overwrite_target,
        )

    def _flatten_values(
        self, source_fields_values: list[FieldValue], deduplicate: bool = True
    ) -> list[FieldValue]:
        duplicates = []
        ordered_flatten_list = []
        flat_source_fields = self._get_flatten_source_fields(source_fields_values)
        for field_value in flat_source_fields:
            if deduplicate and field_value in duplicates:
                continue
            duplicates.append(field_value)
            ordered_flatten_list.append(field_value)

        return ordered_flatten_list

    def _handle_missing_fields(
        self,
        event: dict[str, FieldValue],
        rule: FieldManagerRule,
        source_fields: list[str],
        field_values: list[FieldValue],
        config: FieldManagerRule.Config | None = None,
    ) -> bool:
        if config is None:
            config = rule.config

        if config.ignore_missing_fields:
            return False
        if None in field_values:
            error = self._get_missing_fields_error(source_fields, field_values)
            self._handle_warning_error(
                event,
                rule,
                error,
                failure_tags=[f"_{rule.rule_type}_missing_field_warning"],
            )
            return True
        return False

    @staticmethod
    def _get_field_values(event: dict[str, FieldValue], source: list[str]) -> list[FieldValue]:
        return [get_dotted_field_value(event, source_field) for source_field in source]

    def _get_missing_fields_error(self, source_fields, field_values):
        missing_fields = [key for key, value in zip(source_fields, field_values) if value is None]
        return Exception(f"{self.name}: missing source_fields: {missing_fields}")

    @staticmethod
    def _get_flatten_source_fields(source_fields_values: list[FieldValue]) -> list[FieldValue]:
        flat_source_fields = []
        for item in source_fields_values:
            if isinstance(item, list):
                flat_source_fields.extend(item)
            else:
                flat_source_fields.append(item)
        return flat_source_fields

    @staticmethod
    def _filter_missing_fields(
        source_field_values: list[FieldValue], targets: list[str]
    ) -> tuple[list[FieldValue], list[str]]:
        if None not in source_field_values:
            return source_field_values, targets

        values: list[FieldValue] = []
        filtered_targets: list[str] = []

        for value, target in zip(source_field_values, targets):
            if value is not None:
                values.append(value)
                filtered_targets.append(target)

        return values, filtered_targets

    def transform_values(
        self, source_field_values: list[FieldValue], _event: dict, _rule: FieldManagerRule
    ) -> list[FieldValue]:
        """template method to be able to transform the source fields
        in child classes
        """
        return source_field_values
