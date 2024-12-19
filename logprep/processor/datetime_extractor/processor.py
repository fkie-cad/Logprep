"""
DatetimeExtractor
=================

The `datetime_extractor` is a processor that can extract timestamps from a field and
split it into its parts.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - datetimeextractorname:
        type: datetime_extractor
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.datetime_extractor.processor.DatetimeExtractor.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.datetime_extractor.rule
"""

from datetime import datetime

from logprep.processor.datetime_extractor.rule import DatetimeExtractorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser


class DatetimeExtractor(FieldManager):
    """Split timestamps into fields containing their parts."""

    _local_timezone_name: str

    rule_class = DatetimeExtractorRule

    @staticmethod
    def _get_timezone_name(local_timezone):
        tz_name = datetime.now(local_timezone).strftime("%z")
        local_timezone_name = "UTC"
        if tz_name != "+0000":
            local_timezone_name += f"{tz_name[:-2]}:{tz_name[-2:]}"
        return local_timezone_name

    def _apply_rules(self, event, rule):
        datetime_field = rule.source_fields[0]
        destination_field = rule.target_field

        if self._handle_missing_fields(event, rule, rule.source_fields, [datetime_field]):
            return

        if destination_field:
            datetime_value = get_dotted_field_value(event, datetime_field)

            parsed_timestamp = TimeParser.from_string(datetime_value)

            if parsed_timestamp.tzname() == "UTC":
                timezone = "UTC"
            else:
                timezone = str(parsed_timestamp.tzinfo)

            split_timestamp = {
                "year": parsed_timestamp.year,
                "month": parsed_timestamp.month,
                "day": parsed_timestamp.day,
                "hour": parsed_timestamp.hour,
                "minute": parsed_timestamp.minute,
                "second": parsed_timestamp.second,
                "microsecond": parsed_timestamp.microsecond,
                "weekday": parsed_timestamp.strftime("%A"),
                "timezone": timezone,
            }

            if split_timestamp:
                self._write_target_field(event, rule, split_timestamp)
