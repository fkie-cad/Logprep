# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.replacer.rule import ReplacerRule


class TestReplacerRule:
    def test_create_from_dict_returns_replacer_rule(self):
        rule = {
            "filter": "message",
            "replacer": {
                "mapping": {"test": "this is %{replace this}"},
            },
        }
        rule_dict = ReplacerRule._create_from_dict(rule)
        assert isinstance(rule_dict, ReplacerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this} and %{replace that}"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {},
                    },
                },
                ValueError,
                "Length of 'mapping' must be >= 1",
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "source_fields": ["test"],
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                TypeError,
                "unexpected keyword argument 'source_fields'",
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "target_field": "test",
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                TypeError,
                "unexpected keyword argument 'target_field'",
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "missing replacement pattern"},
                    },
                },
                ValueError,
                "'mapping' must match regex",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                ReplacerRule._create_from_dict(rule)
        else:
            rule_instance = ReplacerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("replacer").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            # add your tests here
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = ReplacerRule._create_from_dict(rule1)
        rule2 = ReplacerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
