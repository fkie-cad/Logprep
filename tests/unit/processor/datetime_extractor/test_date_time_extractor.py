# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from tests.unit.processor.base import BaseProcessorTestCase

pytest.importorskip("logprep.processor.datetime_extractor")

from datetime import datetime
from dateutil.tz import tzlocal, tzutc
from dateutil.parser import parse

from logprep.processor.datetime_extractor.processor import DatetimeExtractor


class TestDatetimeExtractor(BaseProcessorTestCase):

    CONFIG = {
        "type": "datetime_extractor",
        "specific_rules": ["tests/testdata/unit/datetime_extractor/rules/specific"],
        "generic_rules": ["tests/testdata/unit/datetime_extractor/rules/generic"],
    }

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    def test_an_event_extracted_datetime_utc(self):
        assert self.object.ps.processed_count == 0

        timestamp = "2019-07-30T14:37:42.861Z"
        document = {"@timestamp": timestamp, "winlog": {"event_id": 123}}

        self.object.process(document)

        # Two different timezones need to be used in the test to account for daylight savings
        # Use current timezone here, since the processor initializes with timezone on the system
        tz_local_name = datetime.now(tzlocal()).strftime("%z")
        _, _, local_timezone = self._parse_local_tz(tz_local_name)

        # Use timestamps timezone here, since processor uses timezones of each timestamp for deltas
        parsed_timestamp = parse(timestamp).astimezone(tzlocal())
        tz_local_name = parsed_timestamp.strftime("%z")
        ts_hour_delta, ts_minute_delta, _ = self._parse_local_tz(tz_local_name)

        expected = {
            "@timestamp": timestamp,
            "winlog": {"event_id": 123},
            "split_@timestamp": {
                "day": 30,
                "hour": 14 + ts_hour_delta,
                "microsecond": 861000,
                "minute": 37 + ts_minute_delta,
                "month": 7,
                "second": 42,
                "timezone": local_timezone,
                "weekday": "Tuesday",
                "year": 2019,
            },
        }
        assert document == expected

    def test_an_event_extracted_datetime_plus_one(self):
        assert self.object.ps.processed_count == 0

        timestamp = "2019-07-30T14:37:42.861+01:00"
        document = {"@timestamp": timestamp, "winlog": {"event_id": 123}}

        self.object.process(document)

        # Two different timezones need to be used in the test to account for daylight savings
        # Use current timezone here, since the processor initializes with timezone on the system
        tz_local_name = datetime.now(tzlocal()).strftime("%z")
        _, _, local_timezone = self._parse_local_tz(tz_local_name)

        # Use timestamps timezone here, since processor uses timezones of each timestamp for deltas
        parsed_timestamp = parse(timestamp).astimezone(tzlocal())
        tz_local_name = parsed_timestamp.strftime("%z")
        ts_hour_delta, ts_minute_delta, _ = self._parse_local_tz(tz_local_name)

        expected = {
            "@timestamp": timestamp,
            "winlog": {"event_id": 123},
            "split_@timestamp": {
                "day": 30,
                "hour": 13 + ts_hour_delta,  # 13 ist hour of src timestamp in UTC
                "microsecond": 861000,
                "minute": 37 + ts_minute_delta,
                "month": 7,
                "second": 42,
                "timezone": local_timezone,
                "weekday": "Tuesday",
                "year": 2019,
            },
        }
        assert document == expected

    def test_an_event_extracted_datetime_and_local_utc_without_delta(self):
        assert self.object.ps.processed_count == 0

        self.object._local_timezone = tzutc()
        self.object._local_timezone_name = DatetimeExtractor._get_timezone_name(
            self.object._local_timezone
        )

        timestamp = "2019-07-30T14:37:42.861+00:00"
        document = {"@timestamp": timestamp, "winlog": {"event_id": 123}}

        self.object.process(document)

        tz_local_name = "+0000"
        local_hour_delta, local_minute_delta, local_timezone = self._parse_local_tz(tz_local_name)

        expected = {
            "@timestamp": timestamp,
            "winlog": {"event_id": 123},
            "split_@timestamp": {
                "day": 30,
                "hour": 14 + local_hour_delta,
                "microsecond": 861000,
                "minute": 37 + local_minute_delta,
                "month": 7,
                "second": 42,
                "timezone": local_timezone,
                "weekday": "Tuesday",
                "year": 2019,
            },
        }
        assert document == expected

    @staticmethod
    def _parse_local_tz(tz_local_name):
        sign = tz_local_name[:1]
        hour = tz_local_name[1:-2]
        minute = tz_local_name[3:]
        timezone_utc = f"UTC{sign}{hour}:{minute}" if hour != "00" or minute != "00" else "UTC"
        return int(f"{sign}{hour}"), int(f"{sign}{minute}"), timezone_utc
