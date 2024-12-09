# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from logprep.util.time import TimeParser


class TestTimeParser:
    @pytest.mark.parametrize(
        "source, expected",
        [
            ("1999-12-01", {"year": 1999, "month": 12, "day": 1}),
            (
                "2009-06-15T13:45:30.0000000-07:00",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45, "second": 30},
            ),
            (
                "2009-06-15 13:45:30Z",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45, "second": 30},
            ),
            (
                "2012-W05-5",
                {"year": 2012, "month": 2, "day": 3},
            ),
        ],
    )
    def test_from_string(self, source, expected):
        timestamp = TimeParser.from_string(source)
        assert isinstance(timestamp, datetime)
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value

    def test_from_timestamp(self):
        expected = {"year": 1969, "month": 12, "day": 31, "hour": 23, "minute": 59}
        timestamp = TimeParser.from_timestamp(-1)
        assert isinstance(timestamp, datetime)
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value

    def test_now_returns_datetime(self):
        assert isinstance(TimeParser.now(), datetime)

    @pytest.mark.parametrize(
        "source, format_str, expected",
        [
            (
                "Wed Dec 4 1:14:31 PM 2022",
                "%a %b %d %I:%M:%S %p %Y",
                {"year": 2022, "month": 12, "day": 4, "hour": 13, "minute": 14, "second": 31},
            )
        ],
    )
    def test_from_format_returns(self, source, format_str, expected):
        timestamp = TimeParser.from_format(source, format_str)
        assert isinstance(timestamp, datetime)
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value

    @pytest.mark.parametrize("timezone", [None, ZoneInfo("UTC"), ZoneInfo("Europe/Berlin")])
    def test_has_utc_if_timezone_was_set(self, timezone):
        datetime_time = datetime.now(timezone)
        time_parser_time = TimeParser.now(timezone)
        assert time_parser_time.second == pytest.approx(datetime_time.second, abs=1)
        if timezone is None:
            assert time_parser_time.tzinfo == ZoneInfo("UTC")
        else:
            assert time_parser_time.tzinfo == timezone

    def test_set_utc_if_timezone_is_missing_sets_timezone(self):
        datetime_time = datetime.now()
        assert datetime_time.tzinfo is None
        time_parser_time = TimeParser._set_utc_if_timezone_is_missing(datetime_time)
        assert time_parser_time.tzinfo is ZoneInfo("UTC")
        assert time_parser_time.second == pytest.approx(datetime_time.second, abs=1)

    @pytest.mark.parametrize(
        "timestamp, source_format, source_timezone, expected_timezone_name, expected",
        [
            (
                "2021-03-13T11:23:13Z",
                "ISO8601",
                ZoneInfo("Europe/Berlin"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021-03-13T11:23:13Z",
                "ISO8601",
                ZoneInfo("UTC"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021-03-13T11:23:13+01",
                "ISO8601",
                ZoneInfo("UTC"),
                "UTC+01:00",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021-03-13T11:23:13",
                "ISO8601",
                ZoneInfo("UTC"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021 03 13 - 11:23:13",
                "%Y %m %d - %H:%M:%S",
                ZoneInfo("UTC"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021 03 13 - 11:23:13",
                "%Y %m %d - %H:%M:%S",
                ZoneInfo("Europe/Berlin"),
                "CET",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "2021 03 13 - 11:23:13 -03:00",
                "%Y %m %d - %H:%M:%S %z",
                ZoneInfo("Europe/Berlin"),
                "UTC-03:00",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "03 13 - 11:23:13",
                "%m %d - %H:%M:%S",
                ZoneInfo("UTC"),
                "UTC",
                {
                    "year": datetime.now().year,
                    "month": 3,
                    "day": 13,
                    "hour": 11,
                    "minute": 23,
                    "second": 13,
                },
            ),
        ],
    )
    def test_parse_datetime_replaces_timezone_if_it_does_not_exist_in_string(
        self, timestamp, source_format, source_timezone, expected_timezone_name, expected
    ):
        timestamp = TimeParser.parse_datetime(timestamp, source_format, source_timezone)
        assert timestamp.tzinfo.tzname(timestamp) == expected_timezone_name
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value

    @pytest.mark.parametrize(
        "timestamp, source_format, source_timezone, expected_timezone_name, expected",
        [
            (
                "1615634593",
                "UNIX",
                ZoneInfo("UTC"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "1615634593",
                "UNIX",
                ZoneInfo("Europe/Berlin"),
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
        ],
    )
    def test_parse_datetime_unix_timestamp_is_always_utc(
        self, timestamp, source_format, source_timezone, expected_timezone_name, expected
    ):
        timestamp = TimeParser.parse_datetime(timestamp, source_format, source_timezone)
        assert timestamp.tzinfo.tzname(timestamp) == expected_timezone_name
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value

    @pytest.mark.parametrize(
        "timestamp, expected_timezone_name, expected",
        [
            (
                "1615634593",
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "1615634593000",
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
            (
                "1615634593000000",
                "UTC",
                {"year": 2021, "month": 3, "day": 13, "hour": 11, "minute": 23, "second": 13},
            ),
        ],
    )
    def test_parse_unix_timestamp(self, timestamp, expected_timezone_name, expected):
        parsed_timestamp = TimeParser.parse_datetime(timestamp, "UNIX", ZoneInfo("UTC"))
        assert parsed_timestamp.tzinfo.tzname(parsed_timestamp) == expected_timezone_name
        for attribute, value in expected.items():
            assert getattr(parsed_timestamp, attribute) == value
