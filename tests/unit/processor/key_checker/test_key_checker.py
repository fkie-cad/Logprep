# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=import-error
import pytest

from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "writes new fields with same separator",
        {
            "filter": "*",
            "key_checker": {
                "key_list": ["key2"],
                "error_field": "missing_fields",
            },
        },
        {"bla": {"key1": "key1_value", "_index": "value"}},
        {
            "bla": {
                "key1": "key1_value",
                "_index": "value",
            },
            "missing_fields": ["key2"],
        },
    ),
]


class TestKeyChecker(BaseProcessorTestCase):
    timeout = 0.01

    CONFIG = {
        "type": "key_checker",
        "specific_rules": ["tests/testdata/unit/key_checker/"],
        "generic_rules": ["tests/testdata/unit/key_checker/"],
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected
