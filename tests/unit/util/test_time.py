# pylint: disable=missing-docstring
# pylint: disable=protected-access
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

    def test_set_utc_if_timezone_is_missing_sets_timezone(self):
        time_object = datetime.now()
        assert time_object.tzinfo is None
        time_object = TimeParser._set_utc_if_timezone_is_missing(time_object)
        assert time_object.tzinfo is ZoneInfo("UTC")
