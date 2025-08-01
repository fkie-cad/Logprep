"""
Dropper
=======

The `dropper` is a processor that removes fields from log messages. Which fields are deleted is
determined within each rule.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - droppername:
        type: dropper
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.dropper.processor.Dropper.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.dropper.rule
"""

from functools import partial

from logprep.ng.abc.processor import Processor
from logprep.processor.dropper.rule import DropperRule
from logprep.util.helper import get_dotted_field_value, pop_dotted_field_value


class Dropper(Processor):
    """Drop log events."""

    rule_class = DropperRule

    def _apply_rules(self, event: dict, rule: DropperRule) -> None:
        """Drops fields from event Logs."""
        if rule.drop_full:
            drop_function = partial(pop_dotted_field_value, event)
        else:
            drop_function = partial(self._drop, event)
        list(map(drop_function, rule.fields_to_drop))

    @staticmethod
    def _drop(event: dict, dotted_field: str) -> None:
        parent_field, _, key = dotted_field.rpartition(".")
        parent_field_value = get_dotted_field_value(event, parent_field)
        if not parent_field_value:
            return
        if key in parent_field_value:
            parent_field_value.pop(key)
