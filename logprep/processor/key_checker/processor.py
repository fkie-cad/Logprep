"""
KeyChecker
==========

The `key_checker` processor checks if all field names in a provided list are
given in the processed event.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - keycheckername:
        type: key_checker
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.key_checker.processor.KeyChecker.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.key_checker.rule
"""

from typing import Iterable

from logprep.abc.processor import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.key_checker.rule import KeyCheckerRule
from logprep.util.helper import get_dotted_field_value


class KeyChecker(Processor):
    """Checks if all keys of a given List are in the event"""

    rule_class: Rule = KeyCheckerRule

    def _apply_rules(self, event, rule):
        not_existing_fields = list(
            {
                dotted_field
                for dotted_field in rule.source_fields
                if not self._field_exists(event, dotted_field)
            }
        )

        if not not_existing_fields:
            return

        output_value = get_dotted_field_value(event, rule.target_field)

        if isinstance(output_value, Iterable):
            output_value = list({*not_existing_fields, *output_value})
        else:
            output_value = not_existing_fields

        self._write_target_field(event, rule, sorted(output_value))
