# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=import-error

import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "writes missing root-key in the missing_fields Field",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key2"],
                "target_field": "missing_fields",
            },
        },
        {
            "testkey": "key1_value",
            "_index": "value",
        },
        {
            "testkey": "key1_value",
            "_index": "value",
            "missing_fields": ["key2"],
        },
    ),
    (
        "writes missing sub-key in the missing_fields Field",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["testkey.key2"],
                "target_field": "missing_fields",
            },
        },
        {"testkey": {"key1": "key1_value", "_index": "value"}},
        {
            "testkey": {
                "key1": "key1_value",
                "_index": "value",
            },
            "missing_fields": ["testkey.key2"],
        },
    ),
    (
        "writes the missing key from a list with one missing and 3 existing keys in the missing_fields Field",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key1.key2", "key1", "key1.key2.key3", "key4"],
                "target_field": "missing_fields",
            },
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            }
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "missing_fields": ["key4"],
        },
    ),
    (
        "Detects 'root-key1' in the event",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key1"],
                "target_field": "missing_fields",
            },
        },
        {
            "key1": {
                "key2": {"key3": "key3_value", "random_key": "random_key_value"},
                "_index": "value",
            }
        },
        {
            "key1": {
                "key2": {"key3": "key3_value", "random_key": "random_key_value"},
                "_index": "value",
            }
        },
    ),
    (
        "Detects 'sub-key2' in the event",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["testkey.key2"],
                "target_field": "missing_fields",
            },
        },
        {
            "testkey": {
                "key2": {"key3": "key3_value", "random_key": "random_key_value"},
                "_index": "value",
            }
        },
        {
            "testkey": {
                "key2": {"key3": "key3_value", "random_key": "random_key_value"},
                "_index": "value",
            },
        },
    ),
    (
        "Detects multiple Keys",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key1.key2", "key1", "key1.key2.key3"],
                "target_field": "missing_fields",
            },
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            }
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            }
        },
    ),
    (
        "Detect key duplication",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key1", "key1"],
                "target_field": "missing_fields",
            },
        },
        {
            "randomkey": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
        },
        {
            "randomkey": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["key1"],
        },
    ),
    (
        "Detect key duplication2",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["key1", "key1"],
                "target_field": "missing_fields",
            },
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
        },
    ),
    (
        "Extends existing output field list by setting overwrite_target",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["not.existing.key"],
                "target_field": "missing_fields",
                "overwrite_target": True,
            },
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["i.exists.already"],
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["i.exists.already", "not.existing.key"],
        },
    ),
    (
        "Prevents duplicates in output field by setting overwrite_target to True",
        {
            "filter": "*",
            "key_checker": {
                "source_fields": ["not.existing.key"],
                "target_field": "missing_fields",
                "overwrite_target": True,
            },
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["not.existing.key"],
        },
        {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["not.existing.key"],
        },
    ),
]


class TestKeyChecker(BaseProcessorTestCase):
    CONFIG = {
        "type": "key_checker",
        "rules": ["tests/testdata/unit/key_checker/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases_positiv(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_field_exists_warning(self):
        rule_dict = {
            "filter": "*",
            "key_checker": {
                "source_fields": ["not.existing.key"],
                "target_field": "missing_fields",
            },
        }
        self._load_rule(rule_dict)
        document = {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["i.exists.already"],
        }
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
