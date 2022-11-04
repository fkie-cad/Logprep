"""
Concatenator
------------

The `concatenator` processor allows to concat a list of source fields into one new target field. The
concat separator and the target field can be specified. Furthermore, it is possible to directly
delete all given source fields, or to overwrite the specified target field.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - Concatenatorname:
        type: concatenator
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.concatenator.rule import ConcatenatorRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class ConcatenatorError(BaseException):
    """Base class for Concatenator related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"Concatenator ({name}): {message}")


class Concatenator(Processor):
    """Concatenates a list of source fields into a new target field."""

    rule_class = ConcatenatorRule

    def _apply_rules(self, event, rule: ConcatenatorRule):
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

        source_field_values = []
        for source_field in rule.source_fields:
            field_value = get_dotted_field_value(event, source_field)
            source_field_values.append(field_value)

        source_field_values = [field for field in source_field_values if field is not None]
        target_value = f"{rule.separator}".join(source_field_values)

        adding_was_successful = add_field_to(
            event, rule.target_field, target_value, overwrite_output_field=rule.overwrite_target
        )
        if not adding_was_successful:
            raise DuplicationError(self.name, [rule.target_field])
