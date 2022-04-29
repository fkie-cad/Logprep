# pylint: disable=protected-access
# pylint: disable=missing-docstring
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

        assert rule_tree.root.children[0].expression == Exists(["winlog"])
        assert rule_tree.root.children[0].children[0].expression == StringFilterExpression(
            ["winlog"], "123"
        )
        assert rule_tree.root.children[0].children[0].matching_rules == [rule]

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

        assert rule_tree.root.children[0].children[0].children[0].expression == Exists(["xfoo"])
        assert rule_tree.root.children[0].children[0].children[0].children[
            0
        ].expression == StringFilterExpression(["xfoo"], "bar")
        assert rule_tree.root.children[0].children[0].children[0].children[0].matching_rules == [
            rule
        ]

    def test_get_rule_id(self):
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
        assert rule_tree.get_rule_id(rule) == 0

        rule2 = PreDetectorRule._create_from_dict(
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
        rule_tree.add_rule(rule2)
        assert rule_tree.get_rule_id(rule) == 0
        assert rule_tree.get_rule_id(rule2) == 1

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

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]

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

        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Good"}) == [rule]
        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Okay"}) == [rule]
        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Bad"}) == [rule]
        assert rule_tree.get_matching_rules({"foo": "bar"}) == [rule]

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

        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Good", "foo": "bar"}) == [
            rule,
            rule2,
        ]

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
        assert rule_tree.get_matching_rules({"foo": {"bar": "123"}}) == [rule]

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
        assert rule_tree.get_matching_rules({"foo": {"bar": {"test": "123"}}}) == [rule]

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

        assert rule_tree.get_matching_rules({"abc": "DEF", "foo": {"bar": {"test": "567"}}}) == [
            rule
        ]

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

        assert rule_tree.get_matching_rules({"EventID": "1", "winlog": "123"}) == [subrule, rule]

    def test_get_size(self):
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
        assert rule_tree.get_size() == 2

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
        assert rule_tree.get_size() == 4

        rule = PreDetectorRule._create_from_dict(
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
        )
        rule_tree.add_rule(rule)
        assert rule_tree.get_size() == 5

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
        rules_from_rule_tree = rule_tree._get_rules_as_list()
        assert len(rules_from_rule_tree) == 3
        for rule in rules:
            assert rule in rules_from_rule_tree
