# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = []  # testcase, rule, event, expected

failure_test_cases = []  # testcase, rule, event, expected


class TestIpInformer(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "ip_informer",
        "specific_rules": ["tests/testdata/unit/ip_informer/specific/"],
        "generic_rules": ["tests/testdata/unit/ip_informer/generic/"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
