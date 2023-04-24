# pylint: disable=missing-docstring
from datetime import datetime

import pendulum
import pytest

from logprep.util.time import TimeParser


class TestTimeParser:
    @pytest.mark.parametrize(
        "source, expected",
        [
            ("1999-12-01", {"year": 1999, "month": 12, "day": 1}),
            (
                "1999 12 12 - 12:12:22",
                {"year": 1999, "month": 12, "day": 12, "hour": 12, "minute": 12, "second": 22},
            ),
            (
                "Monday, June 15, 2009 1:45 PM",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45},
            ),
            (
                "6/15/2009 1:45 PM",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45},
            ),
            (
                "15/06/2009 13:45",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45},
            ),
            (
                "2009/6/15 13:45",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45},
            ),
            (
                "6/15/2009 1:45:30 PM",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45, "second": 30},
            ),
            (
                "June 15",
                {"year": pendulum.now().year, "month": 6, "day": 15},
            ),
            (
                "2009-06-15T13:45:30.0000000-07:00",
                {"year": 2009, "month": 6, "day": 15, "hour": 13, "minute": 45, "second": 30},
            ),
            (
                "Mon, 15 Jun 2009 20:45:30 GMT",
                {"year": 2009, "month": 6, "day": 15, "hour": 20, "minute": 45, "second": 30},
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
