"""
Dropper
-------

The `dropper` is a processor that removes fields from log messages. Which fields are deleted is
determined within each rule.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - droppername:
        type: dropper
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from functools import reduce
from logging import DEBUG
from logprep.abc.processor import Processor

from logprep.processor.dropper.rule import DropperRule
from logprep.util.helper import pop_dotted_field_value, get_dotted_field_value


class Dropper(Processor):
    """Normalize log events by copying specific values to standardized fields."""

    rule_class = DropperRule

    def _apply_rules(self, event: dict, rule: DropperRule):
        """Drops fields from event Logs."""

        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"{self.describe()} processing matching event")

        if rule.drop_full:
            reduce(self._drop_full, [event, *rule.fields_to_drop])
        else:
            reduce(self._drop, [event, *rule.fields_to_drop])

    @staticmethod
    def _drop(event, dotted_field):
        parent_field, _, key = dotted_field.rpartition(".")
        parent_field_value = get_dotted_field_value(event, parent_field)
        parent_field_value.pop(key)
        return event

    @staticmethod
    def _drop_full(event, dotted_field):
        pop_dotted_field_value(event, dotted_field)
        return event
