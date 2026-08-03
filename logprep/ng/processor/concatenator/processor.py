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
        source_field_values = []
        for source_field in rule.source_fields:
            field_value = get_dotted_field_value(event, source_field)
            source_field_values.append(field_value)
        self._handle_missing_fields(event, rule, rule.source_fields, source_field_values)

        source_field_values = [field for field in source_field_values if field is not None]

        try:
            target_value = f"{rule.separator}".join(source_field_values)  # type: ignore[arg-type]
        except:
            raise

        self._write_target_field(event, rule, target_value)
