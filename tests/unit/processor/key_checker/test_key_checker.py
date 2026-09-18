# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=import-error

import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    pytest.param(  # testcase, rule, event, expected
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
        id="writes_missing_root-key_in_the_missing_fields_Field",
    ),
    pytest.param(
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
        id="writes_missing_sub-key_in_the_missing_fields_Field",
    ),
    pytest.param(
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
        id="detects_multiple_keys",
    ),
    pytest.param(
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
        id="prevents_duplicates_in_output_field_by_setting_overwrite_target_to_True",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
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
        id="writes_the_missing_key_from_a_list_with_one_missing_and_3_existing_keys_in_the_missing_fields_Field",
    ),
    pytest.param(
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
        id="detects_root-key1_in_the_event",
    ),
    pytest.param(
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
        id="detects_sub-key2_in_the_event",
    ),
    pytest.param(
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
        id="detect_key_duplication_1",
    ),
    pytest.param(
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
        id="detect_key_duplication_2",
    ),
    pytest.param(
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
        id="extends_existing_output_field_list_by_setting_overwrite_target",
    ),
)


class TestKeyChecker(BaseProcessorTestCase):
    CONFIG = {
        "type": "key_checker",
        "rules": ["tests/testdata/unit/key_checker/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases_positiv(self, rule, event, expected, context, provision_context):
        provision_context(context)
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
