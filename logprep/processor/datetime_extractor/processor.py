"""
DatetimeExtractor
-----------------

The `datetime_extractor` is a processor that can extract timestamps from a field and
split it into its parts.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - datetimeextractorname:
        type: datetime_extractor
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from datetime import datetime
from logging import Logger

from dateutil.parser import parse
from dateutil.tz import tzlocal

from logprep.abc import Processor
from logprep.processor.datetime_extractor.rule import DateTimeExtractorRule


class DateTimeExtractorError(BaseException):
    """Base class for DateTimeExtractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DateTimeExtractor ({name}): {message}")


class DatetimeExtractor(Processor):
    """Split timestamps into fields containing their parts."""

    __slots__ = ["_local_timezone", "_local_timezone_name"]

    _local_timezone_name: str

    rule_class = DateTimeExtractorRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._local_timezone = tzlocal()
        self._local_timezone_name = self._get_timezone_name(self._local_timezone)

    @staticmethod
    def _get_timezone_name(local_timezone):
        tz_name = datetime.now(local_timezone).strftime("%z")
        local_timezone_name = "UTC"
        if tz_name != "+0000":
            local_timezone_name += f"{tz_name[:-2]}:{tz_name[-2:]}"
        return local_timezone_name

    def _apply_rules(self, event, rule):
        datetime_field = rule.datetime_field
        destination_field = rule.destination_field

        if destination_field and self._field_exists(event, datetime_field):
            datetime_value = self._get_dotted_field_value(event, datetime_field)

            parsed_timestamp = parse(datetime_value).astimezone(self._local_timezone)

            split_timestamp = {
                "year": parsed_timestamp.year,
                "month": parsed_timestamp.month,
                "day": parsed_timestamp.day,
                "hour": parsed_timestamp.hour,
                "minute": parsed_timestamp.minute,
                "second": parsed_timestamp.second,
                "microsecond": parsed_timestamp.microsecond,
                "weekday": parsed_timestamp.strftime("%A"),
                "timezone": self._local_timezone_name,
            }

            if split_timestamp:
                if destination_field not in event.keys():
                    event[destination_field] = split_timestamp
