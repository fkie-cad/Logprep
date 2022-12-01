# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.requester.rule import RequesterRule


class TestFieldManagerRule:
    def test_create_from_dict_returns_requester_rule(self):
        rule = {
            "filter": "message",
            "requester": {"kwargs": {"method": "GET", "url": "http://fancyapi"}},
        }
        rule_dict = RequesterRule._create_from_dict(rule)
        assert isinstance(rule_dict, RequesterRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                RequesterRule._create_from_dict(rule)
        else:
            rule_instance = RequesterRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("requester").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = RequesterRule._create_from_dict(rule1)
        rule2 = RequesterRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
