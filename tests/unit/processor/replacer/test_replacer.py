# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "Basic testcase",
        {
            "filter": "message",
            "replacer": {
                "mapping": {"message": "this is %{replace this}"},
            },
        },
        {"message": "this is test"},
        {"message": "this is replace this"},
    )
]

failure_test_cases = []  # testcase, rule, event, expected


class TestReplacer(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "replacer",
        "specific_rules": ["tests/testdata/unit/replacer/specific_rules"],
        "generic_rules": ["tests/testdata/unit/replacer/generic_rules"],
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
