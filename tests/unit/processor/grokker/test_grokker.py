# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "matches simple grok pattern",
        {"filter": "message", "grokker": {"mapping": {"message": "this is the %{USER:userfield}"}}},
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "userfield": "MyUser586"},
    ),
    (
        "matches simple grok pattern",
        {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is the %{USER:user.subfield}"}},
        },
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "user": {"subfield": "MyUser586"}},
    ),
]

failure_test_cases = []  # testcase, rule, event, expected


class TestGrokker(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "grokker",
        "specific_rules": ["tests/testdata/unit/grokker/specific_rules"],
        "generic_rules": ["tests/testdata/unit/grokker/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
