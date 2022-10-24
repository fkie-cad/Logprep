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
                        "output_field": "",
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
                        "output_field": "",
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
                        "output_field": "",
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
                        "output_field": "",
                    },
                },
                ValueError,
                "Length of 'key_list' must be => 1: 0",
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": "not a list",
                        "output_field": "",
                    },
                },
                TypeError,
                "'key_list' must be <class 'list'",
            ),
            (
                {
                    "filter": "message",
                    "key_checker": {
                        "key_list": [1, 2, 3],
                        "output_field": "",
                    },
                },
                TypeError,
                "'key_list' must be <class 'str'",
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
                assert value == getattr(keychecker_rule._config, key)
