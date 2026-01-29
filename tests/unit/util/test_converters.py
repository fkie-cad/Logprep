import pytest

from logprep.factory_error import InvalidConfigurationError
from logprep.util.converters import convert_ordered_mapping


@pytest.mark.parametrize(
    "input, should_raise",
    [
        ({"pattern": "result"}, False),
        ({"pattern": {"result_one": "result_two"}}, False),
        ({"pattern": "result_one", "pattern2": "result_two"}, False),
        ([{"pattern": "result_one"}, {"pattern2": "result_two"}], False),
        (
            [{"pattern": "result_one", "invalid_pattern2": "invalid"}, {"pattern2": "result_two"}],
            True,
        ),
        (8, True),
        ([{"pattern": "first"}, {"pattern": "overwrite"}], True),
    ],
)
def test_merge_dicts_converter(input, should_raise: bool):
    if should_raise:
        with pytest.raises(InvalidConfigurationError):
            convert_ordered_mapping(input)
    else:
        assert convert_ordered_mapping(input)
