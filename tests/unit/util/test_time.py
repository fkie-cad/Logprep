from datetime import datetime

import pytest

from logprep.util.timestamp import parse_timestamp


class TestParseTimestamp:
    @pytest.mark.parametrize(
        "source, expected",
        [
            ("1999-12-01", {"year": 1999, "month": 12, "day": 1}),
            (
                "1999 12 12 - 12:12:22",
                {"year": 1999, "month": 12, "day": 12, "hour": 12, "minute": 12, "second": 22},
            ),
        ],
    )
    def test_parse_timestamp(self, source, expected):
        timestamp = parse_timestamp(source)
        assert isinstance(timestamp, datetime)
        for attribute, value in expected.items():
            assert getattr(timestamp, attribute) == value
