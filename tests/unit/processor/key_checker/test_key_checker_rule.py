# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=import-error

import pytest
from logprep.processor.key_checker.rule import KeyCheckerRule


class TestKeyCheckerRule:
    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": ["key1", "key2", "key1.key2"],
                        "output_field": "missing_fields",
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": ["key1"],
                        "output_field": "missing_fields",
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": ["key1.key2"],
                        "output_field": "missing_fields",
                    },
                },
                None,
                None,
            ),
            (
                {"filter": "message", "key_checker": {}},
                TypeError,
                "missing 2 required keyword-only arguments: 'key_list' and 'output_field'",
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": [],
                        "output_field": "missing_fields",
                    },
                },
                ValueError,
                "Length of 'key_list' must be => 1: 0",
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": [1, 2, 3],
                        "output_field": "missing_fields",
                    },
                },
                TypeError,
                "'key_list' must be <class 'str'",
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": ["key1"],
                    },
                },
                TypeError,
                "missing 1 required keyword-only argument: 'output_field'",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                KeyCheckerRule._create_from_dict(rule)
        else:
            keychecker_rule = KeyCheckerRule._create_from_dict(rule)
            assert hasattr(keychecker_rule, "_config")
            for key, value in rule.get("key_checker").items():
                assert hasattr(keychecker_rule._config, key)
                temp_list = list(getattr(keychecker_rule._config, key))
                temp_list.sort()
                if isinstance(value, list):
                    temp_list = list(getattr(keychecker_rule._config, key))
                    temp_list.sort()
                    value.sort()
                    assert value == temp_list
                else:
                    assert value == getattr(keychecker_rule._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "should not be equal, because the name is different",
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1"],
                        "output_field": "missing_fields",
                    },
                },
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key2"],
                        "output_field": "missing_fields",
                    },
                },
                False,
            ),
            (
                "should be equal, because only the order has changed",
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1", "key2"],
                        "output_field": "missing_fields",
                    },
                },
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key2", "key1"],
                        "output_field": "missing_fields",
                    },
                },
                True,
            ),
            (
                "should not be equal, because the keys are different",
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1.key2"],
                        "output_field": "missing_fields",
                    },
                },
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1"],
                        "output_field": "missing_fields",
                    },
                },
                False,
            ),
            (
                "should be equal, because unique keys are the same",
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1", "key2", "key2"],
                        "output_field": "missing_fields",
                    },
                },
                {
                    "filter": "*",
                    "key_checker": {
                        "key_list": ["key1", "key1", "key2"],
                        "output_field": "missing_fields",
                    },
                },
                True,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = KeyCheckerRule._create_from_dict(rule1)
        rule2 = KeyCheckerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
