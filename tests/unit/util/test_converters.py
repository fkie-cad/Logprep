"""converters to use with `attrs` fields"""

import pytest

from logprep.factory_error import InvalidConfigurationError
from logprep.util.converters import (
    convert_ordered_mapping_or_skip,
)


@pytest.mark.parametrize(
    "case, should_raise",
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
def test_merge_dicts_converter(case, should_raise: bool):
    if should_raise:
        with pytest.raises(InvalidConfigurationError):
            convert_ordered_mapping_or_skip(case)
    else:
        assert convert_ordered_mapping_or_skip(case)
