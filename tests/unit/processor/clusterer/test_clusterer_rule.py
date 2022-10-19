# pylint: disable=protected-access
# pylint: disable=missing-docstring

import pytest
from logprep.processor.clusterer.rule import ClustererRule, ClustererRuleError


@pytest.fixture()
def rule_definition():
    return {
        "filter": "message",
        "clusterer": {
            "target": "message",
            "pattern": r"test (signature) test",
            "repl": "<+>\1</+>",
        },
        "description": "insert a description text",
    }


class TestClustererRule:
    def test_rules_are_equal(self, rule_definition):
        rule1 = ClustererRule._create_from_dict(rule_definition)

        rule2 = ClustererRule._create_from_dict(rule_definition)

        assert rule1 == rule2

    def test_if_clusterer_data_valid(self, rule_definition):
        rule_definition["clusterer"]["target"] = None
        with pytest.raises(ClustererRuleError, match=r"is not a string"):
            ClustererRule._check_if_clusterer_data_valid(rule_definition)

        del rule_definition["clusterer"]["target"]
        with pytest.raises(ClustererRuleError, match=r"is missing in Clusterer-Rule"):
            ClustererRule._check_if_clusterer_data_valid(rule_definition)

    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "message",
                    "clusterer": {
                        "target": "message",
                        "pattern": r"test (signature) test",
                        "repl": "<+>\1</+>",
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "clusterer": {
                        "target": "message",
                        "pattern": r"test (signature) test",
                        "repl": "<+>\1</+>",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other target",
                {
                    "filter": "message",
                    "clusterer": {
                        "target": "other message",
                        "pattern": r"test (signature) test",
                        "repl": "<+>\1</+>",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other patter",
                {
                    "filter": "message",
                    "clusterer": {
                        "target": "message",
                        "pattern": r"other test (signature) test",
                        "repl": "<+>\1</+>",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other repl",
                {
                    "filter": "message",
                    "clusterer": {
                        "target": "message",
                        "pattern": r"test (signature) test",
                        "repl": "other <+>\1</+>",
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = ClustererRule._create_from_dict(rule_definition)
        rule2 = ClustererRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
