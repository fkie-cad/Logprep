# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.replacer.rule import ReplacerRule


class TestReplacerRule:
    def test_create_from_dict_returns_replacer_rule(self):
        rule = {
            "filter": "message",
            "replacer": {"mapping": {}},
        }
        rule_dict = ReplacerRule._create_from_dict(rule)
        assert isinstance(rule_dict, ReplacerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            # add your tests here
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
