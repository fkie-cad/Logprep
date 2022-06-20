"""
Dropper
-------

The `dropper` is a processor that removes fields from log messages. Which fields are deleted is
determined within each rule.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - pseudonymizername:
        type: dropper
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from logging import DEBUG
from logprep.abc.processor import Processor

from logprep.processor.dropper.rule import DropperRule


class DropperError(BaseException):
    """Base class for Dropper related exceptions."""

    def __init__(self, name, message):
        super().__init__(f"Dropper ({name}): {message}")


class Dropper(Processor):
    """Normalize log events by copying specific values to standardized fields."""

    rule_class = DropperRule

    def _traverse_dict_and_delete(self, dict_: dict, sub_fields, drop_full: bool):
        sub_field = sub_fields[0] if sub_fields else None
        remaining_sub_fields = sub_fields[1:]

        if not remaining_sub_fields and sub_field in dict_.keys():
            del dict_[sub_field]
        if (
            isinstance(dict_, dict)
            and sub_field in dict_
            and (isinstance(dict_[sub_field], dict) and dict_[sub_field])
        ):
            self._traverse_dict_and_delete(dict_[sub_field], remaining_sub_fields, drop_full)
            if dict_[sub_field] == {} and drop_full:
                del dict_[sub_field]

    def _drop_field(self, event: dict, dotted_field: str, drop_full: bool):
        sub_fields = dotted_field.split(".")
        self._traverse_dict_and_delete(event, sub_fields, drop_full)

    def _apply_rules(self, event: dict, rule: DropperRule):
        """Drops fields from event Logs."""

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f"{self.describe()} processing matching event")
        for drop_field in rule.fields_to_drop:
            self._try_dropping_field(event, drop_field, rule.drop_full)

    def _try_dropping_field(self, event: dict, dotted_field: str, drop_full: bool):
        if self._field_exists(event, dotted_field):
            self._drop_field(event, dotted_field, drop_full)
