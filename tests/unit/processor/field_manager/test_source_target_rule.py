# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.base.rule import SourceTargetRule


class TestSourceTargetRule:
    def test_create_from_dict_returns_dissector_rule(self):
        rule = {
            "filter": "message",
            "source_target": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = SourceTargetRule._create_from_dict(rule)
        assert isinstance(rule_dict, SourceTargetRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "source_target": {"source_fields": ["message"], "target_field": "new_field"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "source_target": "im a not valid input",
                },
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            (
                {
                    "filter": "message",
                    "source_target": {"source_field": "message", "target_field": "new_field"},
                },
                TypeError,
                "unexpected keyword argument 'source_field'",
            ),
            (
                {
                    "filter": "message",
                    "source_target": {"source_fields": ["message"], "target_fields": ["new_field"]},
                },
                TypeError,
                "unexpected keyword argument 'target_fields'",
            ),
            (
                {
                    "filter": "message",
                    "source_target": {
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
                    "source_target": {
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
                SourceTargetRule._create_from_dict(rule)
        else:
            rule_instance = SourceTargetRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("source_target").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "equal because the same",
                {
                    "filter": "message",
                    "source_target": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "message",
                    "source_target": {"source_fields": ["message"], "target_field": "new_field"},
                },
                True,
            )
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = SourceTargetRule._create_from_dict(rule1)
        rule2 = SourceTargetRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
