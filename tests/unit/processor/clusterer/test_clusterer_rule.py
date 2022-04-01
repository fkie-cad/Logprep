from logprep.filter.lucene_filter import LuceneFilter

import pytest

pytest.importorskip("logprep.processor.clusterer")

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
        rule1 = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule2 = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, rule_definition):
        rule = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_diff_target = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_diff_pattern = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_diff_repl = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_diff_filter = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_diff_target._target = ["I am different!"]
        rule_diff_pattern._pattern = ["I am different!"]
        rule_diff_repl._repl = ["I am different!"]
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_target
        assert rule != rule_diff_pattern
        assert rule != rule_diff_repl
        assert rule != rule_diff_filter

    def test_rule_creation_from_dict(self, rule_definition):
        rule_from_dict = ClustererRule._create_from_dict(rule_definition)

        expceted_rule = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        assert rule_from_dict == expceted_rule

    def test_tests_always_list(self, rule_definition):
        rule_no_test = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]), rule_definition["clusterer"]
        )

        rule_dict_test = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]),
            rule_definition["clusterer"],
            tests={"foo": "bar"},
        )

        rule_list_test = ClustererRule(
            LuceneFilter.create(rule_definition["filter"]),
            rule_definition["clusterer"],
            tests=[{"foo": "bar"}],
        )

        assert rule_no_test.tests == []
        assert rule_dict_test.tests == [{"foo": "bar"}]
        assert rule_list_test.tests == [{"foo": "bar"}]

    def test_if_clusterer_data_valid(self, rule_definition):
        rule_definition["clusterer"]["target"] = None
        with pytest.raises(ClustererRuleError, match=r"is not a string"):
            ClustererRule._check_if_clusterer_data_valid(rule_definition)

        del rule_definition["clusterer"]["target"]
        with pytest.raises(ClustererRuleError, match=r"is missing in Clusterer-Rule"):
            ClustererRule._check_if_clusterer_data_valid(rule_definition)
