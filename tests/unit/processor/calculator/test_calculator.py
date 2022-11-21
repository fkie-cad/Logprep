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
