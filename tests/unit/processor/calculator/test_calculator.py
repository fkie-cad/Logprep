# pylint: disable=missing-docstring
import pytest
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = [  # testcase, rule, event, expected
    (
        "sums integers",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": 2},
    ),
    (
        "sums integers from single field",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "1"},
        {"message": "This is a message", "field1": "1", "new_field": 2},
    ),
    (
        "sums floats from multiple fields",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}+${field2}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "1.2", "field2": 4.5},
        {"message": "This is a message", "field1": "1.2", "field2": 4.5, "result": 6.7},
    ),
    (
        "multiplies before sum",
        {
            "filter": "message",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2"},
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2", "result": 13},
    ),
]


class TestCalculator(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "calculator",
        "specific_rules": ["tests/testdata/unit/calculator/specific_rules"],
        "generic_rules": ["tests/testdata/unit/calculator/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected
