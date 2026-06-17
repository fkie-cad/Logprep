"""
Deduplicator
============

The `deduplicator` is a processor that removes duplicate values from specified fields.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - deduplicatorname:
        type: deduplicator
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.deduplicator.processor.Deduplicator.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.deduplicator.rule
"""

from logprep.processor.deduplicator.rule import DeduplicatorRule
from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.util.helper import get_dotted_field_value


class Deduplicator(FieldManager):
    """A processor that removes duplicates from lists"""

    rule_class = DeduplicatorRule  # type: ignore

    def _apply_rules(self, event, rule):
        for field in rule.fields:
            value_list = get_dotted_field_value(event, field)
            if not isinstance(value_list, list):
                continue

            unique = []
            for value in value_list:
                if value not in unique:
                    unique.append(value)
            self._write_to_single_target(
                (event, field, [unique]), merge_with_target=False, overwrite_target=True, rule=rule
            )
