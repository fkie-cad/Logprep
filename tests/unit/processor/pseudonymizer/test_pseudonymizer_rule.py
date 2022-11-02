# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.pseudonymizer.rule import PseudonymizeRule


@pytest.fixture(name="specific_rule_definition")
def get_specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
        "pseudonymize": {
            "winlog.event_data.param1": "RE_WHOLE_FIELD",
            "winlog.event_data.param2": "RE_WHOLE_FIELD",
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
                    "pseudonymize": {
                        "winlog.event_data.param1": "RE_WHOLE_FIELD",
                        "winlog.event_data.param2": "RE_WHOLE_FIELD",
                    },
                    "description": "insert a description text",
                },
                True,
            ),
            (
                "not equal cause other filter",
                {
                    "filter": "otherfilter",
                    "pseudonymize": {
                        "winlog.event_data.param1": "RE_WHOLE_FIELD",
                        "winlog.event_data.param2": "RE_WHOLE_FIELD",
                    },
                    "description": "insert a description text",
                },
                False,
            ),
            (
                "not equal cause other pseudonyms",
                {
                    "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
                    "pseudonymize": {
                        "winlog.event_data.param1": "RE_WHOLE_FIELD",
                        "winlog.event_data.paramother": "RE_WHOLE_FIELD",
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
        rule_1 = PseudonymizeRule._create_from_dict(specific_rule_definition)
        rule_2 = PseudonymizeRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
            "pseudonymize": {
                "winlog.event_data.param1": "RE_WHOLE_FIELD",
                "winlog.event_data.param2": "RE_WHOLE_FIELD",
            },
            "url_fields": ["test"],
            "description": "insert a description text",
        }
        with pytest.deprecated_call() as warnings:
            PseudonymizeRule._create_from_dict(rule_dict)
            assert len(warnings.list) == 2
            matches = [warning.message.args[0] for warning in warnings.list]
            assert "Use pseudonymizer.pseudonyms instead" in matches[0]
            assert "Use pseudonymizer.url_fields instead" in matches[1]
