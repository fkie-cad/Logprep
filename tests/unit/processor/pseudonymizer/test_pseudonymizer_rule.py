# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.pseudonymizer.rule import PseudonymizerRule


@pytest.fixture(name="rule_definition")
def get_rule_definition():
    return {
        "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
        "pseudonymizer": {
            "mapping": {
                "winlog.event_data.param1": "RE_WHOLE_FIELD",
                "winlog.event_data.param2": "RE_WHOLE_FIELD",
            }
        },
        "description": "insert a description text",
    }


class TestPseudonomyzerRule:
    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {"filter": "message", "pseudonym": "I'm not under pseudonymizer"},
                InvalidRuleDefinitionError,
                "config not under key pseudonymizer",
            ),
            (
                {"filter": "message", "pseudonymizer": "I'm not a dict"},
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            (
                {"filter": "message", "pseudonymizer": {"mapping": {}}},
                ValueError,
                "Length of 'mapping' must be >= 1: 0",
            ),
            (
                {
                    "filter": "message",
                    "pseudonymizer": {"mapping": {"field": "regex"}},
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                PseudonymizerRule._create_from_dict(rule)
        else:
            rule_instance = PseudonymizerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("pseudonymizer").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "equal cause the same",
                {
                    "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
                    "pseudonymizer": {
                        "mapping": {
                            "winlog.event_data.param1": "RE_WHOLE_FIELD",
                            "winlog.event_data.param2": "RE_WHOLE_FIELD",
                        }
                    },
                    "description": "insert a description text",
                },
                True,
            ),
            (
                "not equal cause other filter",
                {
                    "filter": "otherfilter",
                    "pseudonymizer": {
                        "mapping": {
                            "winlog.event_data.param1": "RE_WHOLE_FIELD",
                            "winlog.event_data.param2": "RE_WHOLE_FIELD",
                        }
                    },
                    "description": "insert a description text",
                },
                False,
            ),
            (
                "not equal cause other pseudonyms",
                {
                    "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
                    "pseudonymizer": {
                        "mapping": {
                            "winlog.event_data.param1": "RE_WHOLE_FIELD",
                            "winlog.event_data.paramother": "RE_WHOLE_FIELD",
                        }
                    },
                    "description": "insert a description text",
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule_1 = PseudonymizerRule._create_from_dict(rule_definition)
        rule_2 = PseudonymizerRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase
