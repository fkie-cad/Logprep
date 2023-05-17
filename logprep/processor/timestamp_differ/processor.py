"""
TimestampDiffer
===============

The `timestamp_differ` can calculate the time difference between two timestamps.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - timestampdiffer_name:
        type: timestamp_differ
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.timestamp_differ.processor.TimestampDiffer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.timestamp_differ.rule
"""
from datetime import datetime
from functools import reduce
from typing import Union

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.timestamp_differ.rule import TimestampDifferRule
from logprep.util.helper import add_field_to, get_source_fields_dict
from logprep.util.time import TimeParser, TimeParserException, UTC


class TimestampDiffer(Processor):
    """A processor that calculates the time difference between two timestamps"""

    rule_class = TimestampDifferRule

    def _apply_rules(self, event, rule):
        source_field_formats = rule.source_field_formats
        source_field_dict = get_source_fields_dict(event, rule)
        if self._has_missing_values(event, rule, source_field_dict):
            return
        diff = None
        try:
            timestamp_objects = map(
                self._create_timestamp_object, source_field_dict.values(), source_field_formats
            )
            diff = reduce(lambda a, b: a - b, timestamp_objects)
        except TimeParserException as error:
            error.args = [
                f"{error.args[0]} Corresponding source fields and values are: {source_field_dict}."
            ]
            self._handle_warning_error(event, rule, error)

        if diff is not None:
            diff = self._apply_output_format(diff, rule)
            add_successful = add_field_to(
                event,
                output_field=rule.target_field,
                content=diff,
                extends_lists=rule.extend_target_list,
                overwrite_output_field=rule.overwrite_target,
            )
            if not add_successful:
                raise FieldExistsWarning(self, rule, event, [rule.target_field])

    @staticmethod
    def _create_timestamp_object(source: Union[str, int], format_str: str) -> datetime:
        if isinstance(source, int):
            return TimeParser.from_timestamp(source).astimezone(UTC)
        if format_str is None:
            return TimeParser.from_string(source).astimezone(UTC)
        return TimeParser.from_format(source, format_str).astimezone(UTC)

    @staticmethod
    def _apply_output_format(diff, rule):
        output_format = rule.output_format
        show_unit = rule.show_unit
        seconds = diff.total_seconds()
        if output_format == "seconds":
            diff = f"{seconds} s" if show_unit else f"{seconds}"
        if output_format == "milliseconds":
            milliseconds = seconds * 1000
            diff = f"{milliseconds} ms" if show_unit else f"{milliseconds}"
        if output_format == "nanoseconds":
            nanoseconds = seconds * 1000000000
            diff = f"{nanoseconds} ns" if show_unit else f"{nanoseconds}"
        return diff
