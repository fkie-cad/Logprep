"""
KeyChecker
------------

The `key_checker` processor checks if all field names in a provided list are
given in the processed event.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - keycheckername:
        type: key_checker
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

"""

from typing import Iterable
from logprep.abc import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.key_checker.rule import KeyCheckerRule
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.processor.base.exceptions import DuplicationError


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

        add_successful = add_field_to(
            event,
            rule.target_field,
            sorted(output_value),
            extends_lists=False,
            overwrite_output_field=rule.overwrite_target,
        )

        if not add_successful:
            raise DuplicationError(self.name, [rule.target_field])
