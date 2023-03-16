# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.pseudonymizer.rule import PseudonymizerRule


@pytest.fixture(name="specific_rule_definition")
def get_specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
        "pseudonymizer": {
            "pseudonyms": {
                "winlog.event_data.param1": "RE_WHOLE_FIELD",
                "winlog.event_data.param2": "RE_WHOLE_FIELD",
            }
        },
        "description": "insert a description text",
    }


class TestPseudonomyzerRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "equal cause the same",
                {
                    "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
                    "pseudonymizer": {
                        "pseudonyms": {
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
                        "pseudonyms": {
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
                        "pseudonyms": {
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
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule_1 = PseudonymizerRule._create_from_dict(specific_rule_definition)
        rule_2 = PseudonymizerRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase
