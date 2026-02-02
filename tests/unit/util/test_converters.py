"""converters to use with `attrs` fields"""

import pytest

from logprep.util.converters import (
    convert_ordered_mapping_or_keep_mapping,
)


@pytest.mark.parametrize(
    ["case", "should_raise"],
    [
        pytest.param({"pattern": "result"}, False, id="keep_mapping"),
        pytest.param(
            {"pattern": {"result_one": "result_two"}}, False, id="keep_mapping_dict_value"
        ),
        pytest.param(
            {"pattern": "result_one", "pattern2": "result_two"},
            False,
            id="keep_mapping_multiple_values",
        ),
        pytest.param(
            [{"pattern": "result_one"}, {"pattern2": "result_two"}],
            False,
            id="convert_sequence_to_dict",
        ),
        pytest.param(
            [{"pattern": "result_one", "invalid_pattern2": "invalid"}, {"pattern2": "result_two"}],
            True,
            id="multiple_keys_in_same_dict",
        ),
        pytest.param(8, True, id="invalid type"),
        pytest.param(
            [{"pattern": "first"}, {"pattern": "overwrite"}], True, id="duplicate_key_in_sequence"
        ),
    ],
)
def test_merge_dicts_converter(case, should_raise: bool):
    if should_raise:
        with pytest.raises(ValueError):
            convert_ordered_mapping_or_keep_mapping(case)
    else:
        assert convert_ordered_mapping_or_keep_mapping(case)
