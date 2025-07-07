# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order

from unittest import mock

from dateutil.tz import tzoffset, tzutc  # type: ignore

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.datetime_extractor.processor import DatetimeExtractor
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestDatetimeExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_datetime_extractor",
        "rules": ["tests/testdata/unit/datetime_extractor/rules"],
    }

    def test_an_event_extracted_datetime_utc(self):
        timestamp = "2019-07-30T14:37:42.861Z"
        document = LogEvent({"@timestamp": timestamp, "winlog": {"event_id": 123}}, original=b"")

        self.object.process(document)

        expected = LogEvent(
            {
                "@timestamp": timestamp,
                "winlog": {"event_id": 123},
                "split_@timestamp": {
                    "day": 30,
                    "hour": 14,
                    "microsecond": 861000,
                    "minute": 37,
                    "month": 7,
                    "second": 42,
                    "timezone": "UTC",
                    "weekday": "Tuesday",
                    "year": 2019,
                },
            },
            original=b"",
        )
        assert document == expected

    def test_an_event_extracted_datetime_missing_field(self):
        document = LogEvent({"@timestamp": None, "winlog": {"event_id": 123}}, original=b"")
        mock_rule = mock.MagicMock()
        with mock.patch.object(self.object, "_handle_missing_fields", return_value=True):
            result = self.object._apply_rules(document, mock_rule)
            assert result is None

    def test_an_event_extracted_datetime_plus_one(self):
        timestamp = "2019-07-30T14:37:42.861+01:00"
        document = LogEvent({"@timestamp": timestamp, "winlog": {"event_id": 123}}, original=b"")

        self.object.process(document)

        expected = LogEvent(
            {
                "@timestamp": timestamp,
                "winlog": {"event_id": 123},
                "split_@timestamp": {
                    "day": 30,
                    "hour": 14,
                    "microsecond": 861000,
                    "minute": 37,
                    "month": 7,
                    "second": 42,
                    "timezone": "UTC+01:00",
                    "weekday": "Tuesday",
                    "year": 2019,
                },
            },
            original=b"",
        )
        assert document == expected

    def test_an_event_extracted_datetime_and_local_utc_without_delta(self):
        self.object._local_timezone = tzutc()
        self.object._local_timezone_name = DatetimeExtractor._get_timezone_name(
            self.object._local_timezone
        )

        timestamp = "2019-07-30T14:37:42.861+00:00"
        document = LogEvent({"@timestamp": timestamp, "winlog": {"event_id": 123}}, original=b"")

        self.object.process(document)

        tz_local_name = "+0000"
        local_hour_delta, local_minute_delta, local_timezone = self._parse_local_tz(tz_local_name)

        expected = LogEvent(
            {
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
            },
            original=b"",
        )
        assert document == expected

    def test_non_utc_timezone(self):
        tz_plus3 = tzoffset(None, 3 * 3600)
        result = DatetimeExtractor._get_timezone_name(tz_plus3)
        assert result == "UTC+03:00"

    def test_deletes_source_field(self):
        document = LogEvent(
            {"@timestamp": "2019-07-30T14:37:42.861+00:00", "winlog": {"event_id": 123}},
            original=b"test_message",
        )
        rule = {
            "filter": "@timestamp",
            "datetime_extractor": {
                "source_fields": ["@timestamp"],
                "target_field": "split_@timestamp",
                "delete_source_fields": True,
            },
            "description": "",
        }
        self._load_rule(rule)
        self.object._local_timezone = tzutc()
        self.object._local_timezone_name = DatetimeExtractor._get_timezone_name(
            self.object._local_timezone
        )
        self.object.process(document)
        expected = LogEvent(
            {
                "winlog": {"event_id": 123},
                "split_@timestamp": {
                    "year": 2019,
                    "month": 7,
                    "day": 30,
                    "hour": 14,
                    "minute": 37,
                    "second": 42,
                    "microsecond": 861000,
                    "weekday": "Tuesday",
                    "timezone": "UTC",
                },
            },
            original=b"test_message",
        )
        assert document == expected

    def test_overwrite_target(self):
        document = LogEvent(
            {"@timestamp": "2019-07-30T14:37:42.861+00:00", "winlog": {"event_id": 123}},
            original=b"",
        )
        rule = {
            "filter": "@timestamp",
            "datetime_extractor": {
                "source_fields": ["@timestamp"],
                "target_field": "@timestamp",
                "overwrite_target": True,
            },
            "description": "",
        }
        self._load_rule(rule)
        self.object._local_timezone = tzutc()
        self.object._local_timezone_name = DatetimeExtractor._get_timezone_name(
            self.object._local_timezone
        )
        self.object.process(document)
        expected = LogEvent(
            {
                "winlog": {"event_id": 123},
                "@timestamp": {
                    "year": 2019,
                    "month": 7,
                    "day": 30,
                    "hour": 14,
                    "minute": 37,
                    "second": 42,
                    "microsecond": 861000,
                    "weekday": "Tuesday",
                    "timezone": "UTC",
                },
            },
            original=b"",
        )
        assert document == expected

    def test_existing_target_raises_if_not_overwrite_target(self):
        document = LogEvent(
            {"@timestamp": "2019-07-30T14:37:42.861+00:00", "winlog": {"event_id": 123}},
            original=b"",
        )
        rule = {
            "filter": "@timestamp",
            "datetime_extractor": {
                "source_fields": ["@timestamp"],
                "target_field": "@timestamp",
                "overwrite_target": False,
            },
            "description": "",
        }
        self._load_rule(rule)
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    @staticmethod
    def _parse_local_tz(tz_local_name):
        sign = tz_local_name[:1]
        hour = tz_local_name[1:-2]
        minute = tz_local_name[3:]
        timezone_utc = f"UTC{sign}{hour}:{minute}" if hour != "00" or minute != "00" else "UTC"
        return int(f"{sign}{hour}"), int(f"{sign}{minute}"), timezone_utc
