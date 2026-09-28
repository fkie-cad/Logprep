# pylint: disable=missing-docstring
# pylint: disable=too-many-positional-arguments

import pytest

from logprep.processor.calculator.ast.exceptions import (
    DivisionByZeroError,
    InvalidSyntaxError,
)
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "1"},
        {"message": "This is a message", "field1": "1", "new_field": 2},
        id="Sums integers from single field",
    ),
    pytest.param(
        {
            "filter": "duration",
            "calculator": {
                "calc": "${duration} * 10e5",
                "target_field": "duration",
                "overwrite_target": True,
            },
        },
        {"duration": "0.01"},
        {"duration": 10000.0},
        id="Time conversion ms -> ns",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is greater than (>)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "MIN(${a},${c}) < ${b} < MAX(${a}, ${c})",
                "target_field": "b_is_in_range",
            },
        },
        {"message": "This is a message", "a": 6, "b": 5, "c": 3},
        {"message": "This is a message", "a": 6, "b": 5, "c": 3, "b_is_in_range": True},
        id="Range check",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "AND(${a} > 6, ${a} % 2)",
                "target_field": "a_is_gt_6_and_odd",
            },
        },
        {"message": "This is a message", "a": 9},
        {"message": "This is a message", "a": 9, "a_is_gt_6_and_odd": True},
        id="Logic example",
    ),
    pytest.param(
        {
            "filter": "duration",
            "calculator": {
                "calc": "${missing_field} * 10e5",
                "target_field": "duration",
                "ignore_missing_fields": True,
            },
        },
        {"duration": "0.01"},
        {"duration": "0.01"},
        id="Ignore missing source fields",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "target",
                "merge_with_target": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2, "target": [1, 5, 3]},
        {"field1": "6", "field2": "4", "field3": 2, "target": [1, 5, 3, 12]},
        id="Extend list",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "field1",
                "overwrite_target": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"field1": 12, "field2": "4", "field3": 2},
        id="overwrites target",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"result": 12},
        id="Delete source fields",
    ),
    pytest.param(
        {
            "filter": "*",
            "calculator": {
                "calc": "${key.field1} + ${key.source.field2} +${key.source.source.field3}",
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"key": {"source": {"source": {"field3": 2}, "field2": 6}, "field1": 4}},
        {"result": 12},
        id="Handles dotted fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "ff"},
        {"message": "This is a message", "field1": "ff", "new_field": 255},
        id="Convert hex to int",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not greater than (>)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>=2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is greater equal (>=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>=3",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not greater equal (>=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is less than (<)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not less than (<)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is less equal (<=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2<=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not less equal (<=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1==1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is equal (==)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1==2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not equal (==)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1!=2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is unequal (!=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1!=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not unequal (!=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1 + 2 < 4",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare arithmetical less than (x+y < Z)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2 ^ 3 > 4",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare expo greater than (x^y > Z)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": 2},
        id="sums integers",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}+${field2}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "1.2", "field2": 4.5},
        {"message": "This is a message", "field1": "1.2", "field2": 4.5, "result": 6.7},
        id="sums floats from multiple fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2"},
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2", "result": 13},
        id="multiplies before sum",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": 8},
        id="do not raise if field value is 0",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": False},
        id="logical evaluates fields to False",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"field1": "6", "field2": "4", "field3": 2, "result": True},
        id="logical evaluates fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "ff"},
        {"message": "This is a message", "field1": "ff", "new_field": 255},
        id="convert hex to int",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "FF"},
        {"message": "This is a message", "field1": "FF", "new_field": 255},
        id="convert hex to int with prefix",
    ),
]

setup_failure_test_cases = [
    pytest.param(
        {
            "filter": "field1",
            "calculator": {
                "calc": "round(${field1}",
                "target_field": "result",
            },
        },
        InvalidSyntaxError,
        id="Tags failure incorrect syntax",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "3/0",
                "target_field": "result",
            },
        },
        DivisionByZeroError,
        id="division by zero in expression",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "3/(1-1)",
                "target_field": "result",
            },
        },
        DivisionByZeroError,
        id="division by zero on optimization",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": " 9^9^9",
                "target_field": "result",
            },
        },
        TimeoutError,
        id="constant raises timeout on setup",
    ),
]

runtime_failure_test_cases = [
    pytest.param(
        {
            "filter": "field1 AND field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "not parsable", "field2": "4", "field3": 2},
        {
            "field1": "not parsable",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        id="Tags failure if parse is not possible",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "5", "field2": "4", "field3": 2, "result": "exists"},
        {
            "field1": "5",
            "field2": "4",
            "field3": 2,
            "result": "exists",
            "tags": ["_calculator_failure"],
        },
        id="Tags failure if target_field exist",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field2": "4", "field3": 2},
        {
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_missing_field_warning"],
        },
        id="Tags failure if source_field missing",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "", "field2": "4", "field3": 2},
        {
            "field1": "",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        id="Tags failure if source_field is empty",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "\"; print('escaped');\"", "field2": "4", "field3": 2},
        {
            "field1": "\"; print('escaped');\"",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        id="Tags failure try to escape",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": " ${a}^${a}^${a}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "a": 9},
        {
            "message": "This is a message",
            "a": 9,
            "tags": ["_calculator_failure"],
        },  # "STREAM ioctl timeout" for MacOS/darwin
        id="raises timeout on runtime",
    ),
]


class TestCalculator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected", runtime_failure_test_cases)
    def test_testcases_failure_handling_at_runtime(self, rule, event, expected):
        self._load_rule(rule)
        self.object.setup()
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert event == expected

    @pytest.mark.parametrize("rule, error_type", setup_failure_test_cases)
    def test_testcases_failure_handling_at_setup(self, rule, error_type):
        with pytest.raises(error_type):
            self._load_rule(rule)
