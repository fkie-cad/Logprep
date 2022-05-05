# pylint: disable=missing-docstring
from unittest import mock
import pytest
from logprep.util.helper import camel_to_snake
from logprep.util.json_handling import is_json


class TestCamelToSnake:
    @pytest.mark.parametrize(
        "camel_case, snake_case",
        [
            ("snakesOnAPlane", "snakes_on_a_plane"),
            ("SnakesOnAPlane", "snakes_on_a_plane"),
            ("snakes_on_a_plane", "snakes_on_a_plane"),
            ("IPhoneHysteria", "i_phone_hysteria"),
            ("iPhoneHysteria", "i_phone_hysteria"),
        ],
    )
    def test_camel_to_snake(self, camel_case, snake_case):
        assert camel_to_snake(camel_case) == snake_case


class TestIsJson:
    @pytest.mark.parametrize(
        "data, expected",
        [
            (
                """
                [
                    { "i": "am json"}
                ]
                """,
                True,
            ),
            (
                """
                key1: valid yaml but not json
                key2:
                    - key3: key3
                """,
                False,
            ),
            (
                """
                [
                    "i": "am not valid json but readable as yaml"
                ]
                """,
                False,
            ),
            (
                """
                filter: test_filter
                processor:
                    key1:
                    - key2: value2
                """,
                False,
            ),
        ],
    )
    def test_is_json_returns_expected(self, data, expected):
        with mock.patch("builtins.open", mock.mock_open(read_data=data)):
            assert is_json("mock_path") == expected
