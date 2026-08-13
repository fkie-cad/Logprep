"""
|PROCESSOR_NAME|
================

The `field_name_replacer` processor replaces characters in dictionary keys.
This can make field names safe to store in systems that, for instance, do not allow dots in keys.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: logprep.processor.field_name_replacer.processor.FieldNameReplacer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.field_name_replacer.rule
"""

import typing
from collections.abc import Callable

from logprep.ng.abc.processor import Processor
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.base.rule import Rule
from logprep.processor.field_name_replacer.rule import (
    FieldNameReplacerRule,
)
from logprep.util.helper import (
    FieldCollisionError,
    FieldValue,
    add_fields_to,
    get_dotted_field_value,
    transform_field_value,
)


class FieldNameReplacer(Processor):
    """Replace configured characters in keys below selected event fields."""

    rule_class = FieldNameReplacerRule

    async def _apply_rules(self, event: dict, rule: Rule) -> None:
        """Apply one rule to the selected parts of an event."""
        rule = typing.cast(FieldNameReplacerRule, rule)

        leaf_handler: Callable[[FieldValue], FieldValue] = lambda leaf: leaf

        for source_field in rule.config.source_fields:
            value = get_dotted_field_value(event, source_field)

            if not isinstance(value, (dict, list)):
                continue

            try:
                transformed = transform_field_value(
                    value,
                    transform_key=rule.replace_key,
                    transform_value=leaf_handler,
                    collision_handler=rule.collision_handler,
                )
            except FieldCollisionError as error:
                raise FieldExistsWarning(rule, event, [error.key]) from error

            add_fields_to(event, {source_field: transformed}, rule=rule, overwrite_target=True)
