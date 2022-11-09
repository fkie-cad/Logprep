# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.generic_adder.rule import GenericAdderRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "add_generic_test",
        "generic_adder": {
            "add": {
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted.added.field": "yet_another_value",
            }
        },
        "description": "",
    }


class TestGenericAdderRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "another_added_field": "another_value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "another_added_field": "another_value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of one key is missing",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same add values",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add_from_file": "tests/testdata/unit/generic_adder/additions_file.yml"
                    },
                },
                True,
            ),
        ],
    )
    def test_rules_equality(
        self,
        specific_rule_definition,
        testcase,
        other_rule_definition,
        is_equal,
    ):
        rule1 = GenericAdderRule._create_from_dict(specific_rule_definition)
        rule2 = GenericAdderRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    def test_rule_accepts_bool_type(self):
        rule_definition = {
            "filter": "add_generic_test",
            "generic_adder": {"add": {"added_bool_field": True}},
        }
        rule = GenericAdderRule._create_from_dict(rule_definition)
        assert isinstance(rule.add.get("added_bool_field"), bool)
