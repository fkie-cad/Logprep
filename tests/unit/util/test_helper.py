import pytest
from logprep.util.helper import camel_to_snake


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
