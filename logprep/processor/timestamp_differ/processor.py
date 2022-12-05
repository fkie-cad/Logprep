"""
TimestampDiffer
===============

# FIXME: Docu
The `timestamp_differ` processor


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - timestampdiffername:
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
        source_field_values = map(partial(get_dotted_field_value, event), source_fields)
        timestamp_objects = []
        for index, timestamp in enumerate(source_field_values):
            if source_field_timestamp_formats[index] is not None:
                timestamp_object = arrow.get(timestamp, source_field_timestamp_formats[index])
            else:
                timestamp_object = arrow.get(timestamp)
            timestamp_objects.append(timestamp_object)
        diff = reduce(lambda a, b: a - b, timestamp_objects)

        if rule.output_format == "seconds":
            diff = diff.seconds
        if rule.output_format == "milliseconds":
            diff = diff.seconds * 1000
        if rule.output_format == "nanoseconds":
            diff = diff.seconds * 1000000000

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
