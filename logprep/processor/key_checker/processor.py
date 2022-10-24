"""
KeyChecker
------------

The `key_checker` processor checks for an event if all field-names in
the given list are in the Event. If thats not the case it......

"""

from logprep.abc import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.key_checker.rule import KeyCheckerRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class KeyCheckerError(BaseException):
    """Base class for KeyChecker related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"KeyChecker ({name}): {message}")


class FieldNotExistingError(KeyCheckerError):
    """Raise if Key in List isnt in Event."""

    def __init__(self, name: str, not_existing_fields: list):
        message = "The following fields arent in the Event Log: "
        for fields in not_existing_fields:
            if fields == not_existing_fields[-1]:
                message += fields
            else:
                message += fields + ", "

        super().__init__(name, message)


class KeyChecker(Processor):
    """Checks if all keys of an given List are in the event"""

    rule_class: Rule = KeyCheckerRule

    def _apply_rules(self, event, rule):

        not_existing_fields = []

        for dotted_field in rule.key_list:
            if not self._field_exists(event=event, dotted_field=dotted_field):
                not_existing_fields.append(dotted_field)

        if not_existing_fields:
            output_field = get_dotted_field_value(event=event, dotted_field="output_field")
            if output_field:
                merged_lists = list(set(output_field).union(set(not_existing_fields)))
                merged_lists.sort()
                add_field_to(event, rule.output_field, merged_lists)
            else:
                not_existing_fields.sort()
                add_field_to(event, rule.output_field, not_existing_fields)
