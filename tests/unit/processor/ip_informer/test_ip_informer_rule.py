# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.ip_informer.rule import IpInformerRule


class TestIpInformerRule:
    def test_create_from_dict_returns__rule(self):
        rule = {
            "filter": "message",
            "": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = IpInformerRule._create_from_dict(rule)
        assert isinstance(rule_dict, IpInformerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            # add your tests here
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                IpInformerRule._create_from_dict(rule)
        else:
            rule_instance = IpInformerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("field_manager").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            # add your tests here
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = IpInformerRule._create_from_dict(rule1)
        rule2 = IpInformerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase