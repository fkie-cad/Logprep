"""
|PROCESSOR_NAME|
================

The `concatenator` processor allows to concat a list of source fields into one new target field. The
concat separator and the target field can be specified. Furthermore, it is possible to directly
delete all given source fields, or to overwrite the specified target field.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - Concatenatorname:
        type: concatenator
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.concatenator.processor.Concatenator.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.concatenator.rule
"""

import typing

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.rule import Rule
from logprep.processor.concatenator.rule import ConcatenatorRule
from logprep.util.helper import (
    FieldValue,
    get_dotted_field_value,
    get_dotted_field_values,
)


class Concatenator(FieldManager):
    """Concatenates a list of source fields into a new target field."""

    rule_class = ConcatenatorRule

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        """
        Apply matching rule to given log event.
        In the process of doing so, concat all found source fields into the new target field,
        separated by a given separator.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied concatenator rule.
        """
        rule = typing.cast(ConcatenatorRule, rule)

        source_field_values = get_dotted_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, rule.source_fields, source_field_values)

        string_values = [
            field_value for field_value in source_field_values if isinstance(field_value, str)
        ]

        target_value = rule.separator.join(string_values)
        self._write_target_field(event, rule, target_value)
