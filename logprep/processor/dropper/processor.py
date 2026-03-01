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

import typing

from logprep.abc.processor import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.dropper.rule import DropperRule
from logprep.util.helper import pop_dotted_field_value


class Dropper(Processor):
    """Drop log events."""

    rule_class = DropperRule

    def _apply_rules(self, event: dict, rule: Rule):
        """Drops fields from event Logs."""
        rule = typing.cast(DropperRule, rule)
        for dotted_field in rule.fields_to_drop:
            pop_dotted_field_value(event, dotted_field, rule.drop_full)
