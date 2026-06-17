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

import typing

from logprep.ng.abc.processor import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.deduplicator.rule import DeduplicatorRule
from logprep.util.helper import get_dotted_field_value, add_fields_to


class Deduplicator(Processor):
    """A processor that removes duplicates from lists"""

    rule_class = DeduplicatorRule  # type: ignore

    def _apply_rules(self, event: dict, rule: Rule):
        rule = typing.cast(DeduplicatorRule, rule)
        for field in rule.fields:
            value_list = get_dotted_field_value(event, field)
            if not isinstance(value_list, list):
                continue

            unique = []
            for value in value_list:
                if value not in unique:
                    unique.append(value)
            add_fields_to(event, {field: unique}, rule, False, True)
