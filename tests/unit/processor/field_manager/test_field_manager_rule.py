# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule


class TestFieldManagerRule:
    def test_create_from_dict_returns_field_manager_rule(self):
        rule = {
            "filter": "message",
            "field_manager": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = FieldManagerRule._create_from_dict(rule)
        assert isinstance(rule_dict, FieldManagerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "field_manager": {"source_fields": ["message"], "target_field": "new_field"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "field_manager": "im a not valid input",
                },
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            (
                {
                    "filter": "message",
                    "field_manager": {"source_field": "message", "target_field": "new_field"},
                },
                TypeError,
                "unexpected keyword argument 'source_field'",
            ),
            (
                {
                    "filter": "message",
                    "field_manager": {"source_fields": ["message"], "target_fields": ["new_field"]},
                },
                TypeError,
                "unexpected keyword argument 'target_fields'",
            ),
            (
                {
                    "filter": "message",
                    "field_manager": {
                        "source_fields": ["message"],
                        "target_field": "new_field",
                        "overwrite_target": "yes",
                    },
                },
                TypeError,
                "'overwrite_target' must be <class 'bool'>",
            ),
            (
                {
                    "filter": "message",
                    "field_manager": {
                        "source_fields": ["message"],
                        "target_field": "new_field",
                        "delte_source_field": True,
                    },
                },
                TypeError,
                "got an unexpected keyword argument 'delte_source_field'",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                FieldManagerRule._create_from_dict(rule)
        else:
            rule_instance = FieldManagerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("field_manager").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "equal because the same",
                {
                    "filter": "message",
                    "field_manager": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "message",
                    "field_manager": {"source_fields": ["message"], "target_field": "new_field"},
                },
                True,
            )
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = FieldManagerRule._create_from_dict(rule1)
        rule2 = FieldManagerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
