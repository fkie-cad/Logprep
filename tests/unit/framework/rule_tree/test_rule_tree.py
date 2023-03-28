# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long

from logprep.filter.expression.filter_expression import Exists, StringFilterExpression
from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.pre_detector.rule import PreDetectorRule


class TestRuleTree:
    def test_init(self):
        rule_tree = RuleTree()

        assert isinstance(rule_tree.root, Node)
        assert rule_tree.root.expression == "root"

    def test_add_rule(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        node = rule_tree.root.children.popitem()[0]
        assert node.expression == Exists("winlog")
        node = node.children.popitem()[0]
        assert node.expression == StringFilterExpression("winlog", "123")
        assert rule in node.matching_rules
        assert len(node.matching_rules) == 1

        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND xfoo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        node = rule_tree.root.children.popitem()[0].children.popitem()[0].children.popitem()[0]
        assert node.expression == Exists("xfoo")
        node = node.children.popitem()[0]
        assert node.expression == StringFilterExpression("xfoo", "bar")
        assert rule in node.matching_rules
        assert len(node.matching_rules) == 1

    def test_match_simple(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule in rule_tree.get_matching_rules({"winlog": "123"})

    def test_match_complex_case(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule in rule_tree.get_matching_rules({"winlog": "123", "test": "Good"})
        assert rule in rule_tree.get_matching_rules({"winlog": "123", "test": "Okay"})
        assert rule in rule_tree.get_matching_rules({"winlog": "123", "test": "Bad"})
        assert rule in rule_tree.get_matching_rules({"foo": "bar"})

    def test_match_event_matches_multiple_rules(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND test: (Good OR Okay OR Bad)",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        rule2 = PreDetectorRule._create_from_dict(
            {
                "filter": "foo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule2)
        matchings_rules = rule_tree.get_matching_rules(
            {"winlog": "123", "test": "Good", "foo": "bar"}
        )
        assert matchings_rules == {rule: None, rule2: None}

    def test_match_rule_once_with_conjunction_like_sub_rule(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog OR winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == {rule: None}

    def test_match_rule_once_with_conjunction_same(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 OR winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == {rule: None}

    def test_match_rule_once_with_conjunction_both_match(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "foo: 123 OR bar: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"foo": "123", "bar": "123"}) == {rule: None}

    def test_match_rule_with_conjunction_for_different_events(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 OR winlog: 456",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == {rule: None}
        assert rule_tree.get_matching_rules({"winlog": "456"}) == {rule: None}

    def test_match_two_identical_rules(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == {rule: None}

    def test_get_matching_rules_has_deterministic_order(self):
        rule_tree = RuleTree()
        test_rules = 5
        for i in range(test_rules):
            rule = PreDetectorRule._create_from_dict(
                {
                    "filter": "foo: 123 OR bar: 123",
                    "pre_detector": {
                        "id": i,
                        "title": f"{i}",
                        "severity": "0",
                        "case_condition": "directly",
                        "mitre": [],
                    },
                }
            )
            rule_tree.add_rule(rule)

        matching_rules = rule_tree.get_matching_rules({"foo": "123", "bar": "123"})
        rule_ids = [rule.detection_data["id"] for rule in matching_rules]
        assert rule_ids == list(range(test_rules))

    def test_match_exists_filter_is_subfield(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "foo.bar: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)
        assert rule_tree.get_matching_rules({"foo": {"bar": "123"}}) == {rule: None}

        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "foo.bar.test: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)
        assert rule_tree.get_matching_rules({"foo": {"bar": {"test": "123"}}}) == {rule: None}

        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "abc: DEF AND foo.bar.test: 567",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        matching_rules = rule_tree.get_matching_rules(
            {"abc": "DEF", "foo": {"bar": {"test": "567"}}}
        )
        assert matching_rules == {rule: None}

    def test_match_including_tags(self):
        tag_map = {"winlog": "WINDOWS"}

        rule_tree = RuleTree()
        rule_tree.tag_map = tag_map
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )

        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"foo": "bar"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Good"})
        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Good", "WINDOWS": "foo"})

        tag_map = {"winlog": "source.windows"}

        rule_tree = RuleTree()
        rule_tree.tag_map = tag_map
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )

        rule_tree.add_rule(rule)

        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay", "source": "foo"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay", "windows": "foo"})
        assert rule_tree.get_matching_rules(
            {"winlog": "123", "test": "Okay", "source": {"windows": "foo"}}
        )

    def test_match_with_subrules(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "EventID: 1 AND winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)

        subrule = PreDetectorRule._create_from_dict(
            {
                "filter": "EventID: 1",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(subrule)

        assert rule_tree.get_matching_rules({"EventID": "1", "winlog": "123"}) == {
            subrule: None,
            rule: None,
        }

    def test_get_rules_as_list(self):
        rule_tree = RuleTree()
        rules = [
            PreDetectorRule._create_from_dict(
                {
                    "filter": "winlog: 123",
                    "pre_detector": {
                        "id": 1,
                        "title": "1",
                        "severity": "0",
                        "case_condition": "directly",
                        "mitre": [],
                    },
                }
            ),
            PreDetectorRule._create_from_dict(
                {
                    "filter": "winlog: 123 AND xfoo: bar",
                    "pre_detector": {
                        "id": 1,
                        "title": "1",
                        "severity": "0",
                        "case_condition": "directly",
                        "mitre": [],
                    },
                }
            ),
            PreDetectorRule._create_from_dict(
                {
                    "filter": "winlog: 123 AND xfoo: foo",
                    "pre_detector": {
                        "id": 1,
                        "title": "1",
                        "severity": "0",
                        "case_condition": "directly",
                        "mitre": [],
                    },
                }
            ),
        ]
        _ = [rule_tree.add_rule(rule) for rule in rules]
        rules_from_rule_tree = rule_tree.rules
        assert len(rules_from_rule_tree) == 3
        for rule in rules:
            assert rule in rules_from_rule_tree

    def test_rule_tree_metrics_counts_number_of_rules(self):
        rule_tree = RuleTree()
        assert rule_tree.metrics.number_of_rules == 0
        rule_tree.add_rule(
            PreDetectorRule._create_from_dict(
                {
                    "filter": "winlog: 123",
                    "pre_detector": {
                        "id": 1,
                        "title": "1",
                        "severity": "0",
                        "case_condition": "directly",
                        "mitre": [],
                    },
                }
            )
        )
        assert rule_tree.metrics.number_of_rules == 1

    def test_rule_tree_metrics_number_of_matches_returns_number_of_all_rule_matches(self):
        rule_tree = RuleTree()
        rule_one = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_one.metrics._number_of_matches = 1
        rule_two = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND xfoo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_two.metrics._number_of_matches = 2
        rule_tree.add_rule(rule_one)
        rule_tree.add_rule(rule_two)
        assert rule_tree.metrics.number_of_matches == 1 + 2

    def test_rule_tree_metrics_mean_processing_time_returns_mean_of_all_rule_mean_processing_times(
        self,
    ):
        rule_tree = RuleTree()
        rule_one = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_one.metrics.update_mean_processing_time(1)
        rule_two = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 123 AND xfoo: bar",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_two.metrics.update_mean_processing_time(2)
        rule_tree.add_rule(rule_one)
        rule_tree.add_rule(rule_two)
        assert rule_tree.metrics.mean_processing_time == 1.5

    def test_rule_tree_metrics_mean_processing_time_returns_zero_if_no_times_available(self):
        rule_tree = RuleTree()
        assert rule_tree.metrics.mean_processing_time == 0.0

    def test_no_rules_for_empty_documents(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "*",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)
        assert not rule_tree.get_matching_rules({})

    def test_adding_rule_twice_does_not_change_size(self):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "*",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        rule_tree.add_rule(rule)
        assert rule_tree.size == 1
        rule_tree.add_rule(rule)
        assert rule_tree.size == 1
