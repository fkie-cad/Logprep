"""
|PROCESSOR_NAME|
================

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

from logprep.abc.processor import Processor
from logprep.processor.key_checker.rule import KeyCheckerRule
from logprep.util.helper import FieldValue, get_dotted_field_value
from logprep.util.typing import is_list_of


class KeyChecker(Processor):
    """Checks if all keys of a given List are in the event"""

    rule_class = KeyCheckerRule

    def _apply_rules(self, event: dict[str, FieldValue], rule: KeyCheckerRule):
        missing_fields = {
            dotted_field
            for dotted_field in rule.source_fields
            if not self._field_exists(event, dotted_field)
        }

        if not missing_fields:
            return

        existing_value: FieldValue = get_dotted_field_value(event, rule.target_field)

        if isinstance(existing_value, list) and is_list_of(existing_value, str):
            missing_fields.update(existing_value)

        self._write_target_field(event, rule, sorted(missing_fields))
