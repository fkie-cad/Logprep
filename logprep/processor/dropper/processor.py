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

from functools import partial
from logprep.abc.processor import Processor

from logprep.processor.dropper.rule import DropperRule
from logprep.util.helper import pop_dotted_field_value, get_dotted_field_value


class Dropper(Processor):
    """Drop log events."""

    rule_class = DropperRule

    def _apply_rules(self, event: dict, rule: DropperRule):
        """Drops fields from event Logs."""
        if rule.drop_full:
            drop_function = partial(pop_dotted_field_value, event)
        else:
            drop_function = partial(self._drop, event)
        list(map(drop_function, rule.fields_to_drop))

    @staticmethod
    def _drop(event, dotted_field):
        parent_field, _, key = dotted_field.rpartition(".")
        parent_field_value = get_dotted_field_value(event, parent_field)
        if not parent_field_value:
            return
        if key in parent_field_value:
            parent_field_value.pop(key)
