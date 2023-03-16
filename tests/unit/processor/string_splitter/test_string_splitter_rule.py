# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.string_splitter.rule import StringSplitterRule


class TestStringSplitterRule:
    def test_create_from_dict_returns_rule(self):
        rule = {
            "filter": "message",
            "string_splitter": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = StringSplitterRule._create_from_dict(rule)
        assert isinstance(rule_dict, StringSplitterRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "string_splitter": {"source_fields": ["message"], "target_field": "message"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "string_splitter": {"source_fields": ["message"], "target_field": "message"},
                    "delimeter": ",",
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                StringSplitterRule._create_from_dict(rule)
        else:
            rule_instance = StringSplitterRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("string_splitter").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            # add your tests here
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = StringSplitterRule._create_from_dict(rule1)
        rule2 = StringSplitterRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
