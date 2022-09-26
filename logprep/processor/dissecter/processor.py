"""
Dissecter
---------

The `dissecter` is a processor that tokenizes incoming strings using defined patterns.
The behavior is based of the logstash dissect filter plugin.
Additionaly it can be used to convert datatypes in messages.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - dissectername:
        type: dissecter
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from logprep.abc import Processor
from logprep.processor.dissecter.rule import DissecterRule
from logprep.util.helper import get_dotted_field_value, add_field_to
from logprep.processor.base.exceptions import ProcessingWarning


class Dissecter(Processor):
    """A processor that tokenizes field values to new fields and converts datatypes"""

    rule_class = DissecterRule

    def _apply_rules(self, event, rule):
        current_field = None
        actions = []
        for source_field, seperator, target_field, action, position in rule.actions:
            if current_field != source_field:
                current_field = source_field
                loop_content = get_dotted_field_value(event, current_field)
                if loop_content is None:
                    self._handle_warning_error(
                        event,
                        rule,
                        BaseException(f"dissecter: mapping field '{source_field}' does not exist"),
                    )
            if seperator:
                content, _, loop_content = loop_content.partition(seperator)
            else:
                content = loop_content
            actions.append((action, event, target_field, content, seperator, position))
        if actions:
            actions.sort(key=lambda x: x[5])  # sort by position
            for action, event, target_field, content, seperator, _ in actions:
                action(event, target_field, content, seperator)
        for target_field, converter in rule.convert_actions:
            try:
                target_value = converter(get_dotted_field_value(event, target_field))
                add_field_to(event, target_field, target_value, overwrite_output_field=True)
            except ValueError as error:
                self._handle_warning_error(event, rule, error)

    @staticmethod
    def _handle_warning_error(event, rule, error):
        add_field_to(event, "tags", rule.failure_tags, extends_lists=True)
        raise ProcessingWarning(str(error)) from error
