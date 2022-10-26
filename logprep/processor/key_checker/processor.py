"""
KeyChecker
------------

The `key_checker` processor checks for an event if all field-names in
the given list are in the Event.

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

from logprep.abc import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.key_checker.rule import KeyCheckerRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class KeyChecker(Processor):
    """Checks if all keys of a given List are in the event"""

    rule_class: Rule = KeyCheckerRule

    def _apply_rules(self, event, rule):

        not_existing_fields = set()

        for dotted_field in rule.key_list:
            if not self._field_exists(event=event, dotted_field=dotted_field):
                not_existing_fields.add(dotted_field)

        if not_existing_fields:
            output_field = get_dotted_field_value(event=event, dotted_field="output_field")
            if output_field:
                missing_fields = list(set(output_field).union(not_existing_fields))
                missing_fields.sort()
                add_field_to(
                    event,
                    rule.output_field,
                    missing_fields,
                )
            else:
                missing_fields = list(not_existing_fields)
                missing_fields.sort()
                add_field_to(event, rule.output_field, missing_fields)
