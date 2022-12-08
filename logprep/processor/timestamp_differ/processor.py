"""
TimestampDiffer
===============

The `timestamp_differ` can calculate the time difference between two timestamps.
For further information for the rule language see: :ref:`timestamp_differ_rule`.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - timestampdiffer_name:
        type: timestamp_differ
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from functools import partial, reduce

import arrow

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.timestamp_differ.rule import TimestampDifferRule
from logprep.util.helper import get_dotted_field_value, add_field_to


class TimestampDiffer(Processor):
    """A processor that calculates the time difference between two timestamps"""

    rule_class = TimestampDifferRule

    def _apply_rules(self, event, rule):
        source_fields, source_field_timestamp_formats = list(zip(*rule.source_fields))
        source_field_values = list(map(partial(get_dotted_field_value, event), source_fields))
        source_field_dict = dict(zip(source_fields, source_field_values))
        self._check_for_missing_values(event, rule, source_field_dict)
        try:
            timestamp_objects = map(arrow.get, source_field_values, source_field_timestamp_formats)
            diff = reduce(lambda a, b: a - b, timestamp_objects)
        except arrow.parser.ParserMatchError as error:
            self._handle_warning_error(event, rule, error)

        diff = self._apply_output_format(diff, rule)
        add_successful = add_field_to(
            event,
            output_field=rule.target_field,
            content=diff,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
        if not add_successful:
            error = DuplicationError(self.name, [rule.target_field])
            self._handle_warning_error(event, rule, error)

    @staticmethod
    def _apply_output_format(diff, rule):
        if rule.output_format == "seconds":
            diff = f"{diff.seconds} s"
        if rule.output_format == "milliseconds":
            diff = f"{diff.seconds * 1000} ms"
        if rule.output_format == "nanoseconds":
            diff = f"{diff.seconds * 1000000000} ns"
        return diff
