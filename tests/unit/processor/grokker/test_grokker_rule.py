# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.grokker.rule import GrokkerRule


class TestGrokkerRule:
    def test_create_from_dict_returns_grokker_rule(self):
        rule = {
            "filter": "message",
            "grokker": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = GrokkerRule._create_from_dict(rule)
        assert isinstance(rule_dict, GrokkerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            # add your tests here
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                GrokkerRule._create_from_dict(rule)
        else:
            rule_instance = GrokkerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("grokker").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            # add your tests here
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = GrokkerRule._create_from_dict(rule1)
        rule2 = GrokkerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase