# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import json
from copy import deepcopy
from unittest import mock

import pytest

from logprep.filter.expression.filter_expression import Exists, StringFilterExpression
from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util import getter


@pytest.fixture(name="rule_dict")
def rule_dict_fixture():
    rule_dict = {
        "filter": "winlog: 123",
        "pre_detector": {
            "id": 1,
            "title": "1",
            "severity": "0",
            "case_condition": "directly",
            "mitre": [],
        },
    }

    return rule_dict


class TestRuleTree:
    def test_init_without_specifying_parameters(self):
        rule_tree = RuleTree()
        assert isinstance(rule_tree.root, Node)
        assert not rule_tree.rule_parser._rule_tagger._tag_map
        assert not rule_tree.tree_config.priority_dict
        assert rule_tree.root.expression is None

    def test_init_with_specifying_config(self):
        rule_tree = RuleTree(config="tests/testdata/unit/tree_config.json")
        assert isinstance(rule_tree.root, Node)
        assert rule_tree.rule_parser._rule_tagger._tag_map == {
            "field_name_to_check_for_in_rule": "TAG-TO-CHECK-IF-IN-EVENT"
        }
        assert rule_tree.tree_config.priority_dict == {"field_name": "priority"}

    @pytest.mark.parametrize(
        "tree_config",
        [
            {
                "priority_dict": {
                    "winlog": 1,  # should be string
                },
                "tag_map": {"field_name_to_check_for_in_rule": "TAG-TO-CHECK-IF-IN-EVENT"},
            },
            {
                "priority_dict": {
                    "winlog": "1",
                },
                "tag_map": {"field_name_to_check_for_in_rule": 1},  # should be string
            },
        ],
    )
    def test_init_with_invalid_tree_config(self, tmp_path, tree_config):
        tree_config_path = tmp_path / "tree_config.json"
        tree_config_path.write_text(json.dumps(tree_config))
        config_data = getter.GetterFactory.from_string(str(tree_config_path)).get_json()
        with pytest.raises(TypeError, match=r"must be \<class \'str\'\>"):
            self.tree_config = RuleTree.Config(**config_data)

    def test_add_rule(self, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.root.children[0].expression == Exists(["winlog"])
        assert rule_tree.root.children[0].children[0].expression == StringFilterExpression(
            ["winlog"], "123"
        )
        assert rule_tree.root.children[0].children[0].matching_rules == [rule]

        rule_dict["filter"] = "winlog: 123 AND xfoo: bar"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.root.children[0].children[0].children[0].expression == Exists(["xfoo"])
        assert rule_tree.root.children[0].children[0].children[0].children[
            0
        ].expression == StringFilterExpression(["xfoo"], "bar")
        assert rule_tree.root.children[0].children[0].children[0].children[0].matching_rules == [
            rule
        ]

    @mock.patch("logging.Logger.warning")
    def test_add_rule_fails(self, mock_warning, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        error = Exception("mocked error")
        with mock.patch(
            "logprep.framework.rule_tree.rule_parser.RuleParser.parse_rule",
            side_effect=error,
        ):
            rule_tree.add_rule(rule)
        mock_warning.assert_called_with(
            'Error parsing rule "%s.yml": %s: %s. Ignore and continue with next rule.',
            None,
            type(error).__name__,
            error,
        )

    def test_get_rule_id(self, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        assert rule_tree.get_rule_id(rule) == 0

        rule_dict["filter"] = "winlog: 123 AND xfoo: bar"
        rule2 = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule2)
        assert rule_tree.get_rule_id(rule) == 0
        assert rule_tree.get_rule_id(rule2) == 1

        rule_dict["filter"] = "winlog: 123 AND xfoo: baz"
        rule3 = PreDetectorRule._create_from_dict(rule_dict)
        assert rule_tree.get_rule_id(rule) == 0
        assert rule_tree.get_rule_id(rule2) == 1
        assert rule_tree.get_rule_id(rule3) is None

    def test_match_simple(self, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]

    @pytest.mark.parametrize(
        "document",
        [
            {"winlog": "123", "test": "Good"},
            {"winlog": "123", "test": "Okay"},
            {"winlog": "123", "test": "Bad"},
            {"foo": "bar"},
        ],
    )
    def test_match_complex_case(self, rule_dict, document):
        rule_tree = RuleTree()
        rule_dict["filter"] = "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules(document) == [rule]

    def test_match_event_matches_multiple_rules(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "winlog: 123 AND test: (Good OR Okay OR Bad)"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        rule_dict["filter"] = "foo: bar"
        rule2 = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule2)

        matchings_rules = rule_tree.get_matching_rules(
            {"winlog": "123", "test": "Good", "foo": "bar"}
        )
        assert matchings_rules == [rule, rule2]

    def test_match_rule_once_with_conjunction_like_sub_rule(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "winlog OR winlog: 123"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]

    def test_match_rule_once_with_conjunction_same(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "winlog: 123 OR winlog: 123"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]

    def test_match_rule_once_with_conjunction_both_match(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "foo: 123 OR bar: 123"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"foo": "123", "bar": "123"}) == [rule]

    def test_match_rule_with_conjunction_for_different_events(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "winlog: 123 OR winlog: 456"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]
        assert rule_tree.get_matching_rules({"winlog": "456"}) == [rule]

    def test_match_two_identical_rules(self, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"winlog": "123"}) == [rule]

    def test_get_matching_rules_has_deterministic_order(self, rule_dict):
        rule_tree = RuleTree()
        test_rules = 5
        rule_dict["filter"] = "foo: 123 OR bar: 123"
        for i in range(test_rules):
            rule_dict["pre_detector"]["id"] = i
            rule_dict["pre_detector"]["title"] = f"{i}"
            rule = PreDetectorRule._create_from_dict(rule_dict)
            rule_tree.add_rule(rule)

        matching_rules = rule_tree.get_matching_rules({"foo": "123", "bar": "123"})
        rule_ids = [rule.detection_data["id"] for rule in matching_rules]
        assert rule_ids == list(range(test_rules))

    @pytest.mark.parametrize(
        "rule_filter, document",
        [
            ("foo.bar: 123", {"foo": {"bar": "123"}}),
            ("foo.bar.test: 123", {"foo": {"bar": {"test": "123"}}}),
            ("abc: DEF AND foo.bar.test: 567", {"abc": "DEF", "foo": {"bar": {"test": "567"}}}),
        ],
    )
    def test_match_exists_filter_is_subfield(self, rule_filter, document, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = rule_filter
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        assert rule_tree.get_matching_rules(document) == [rule]

    def test_match_including_tags(self, rule_dict):
        tag_map = {"winlog": "WINDOWS"}

        rule_tree = RuleTree()
        rule_tree.rule_parser = RuleParser(tag_map)

        rule_dict["filter"] = "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        assert rule_tree.get_matching_rules({"foo": "bar"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Good"})
        assert rule_tree.get_matching_rules({"winlog": "123", "test": "Good", "WINDOWS": "foo"})

        tag_map = {"winlog": "source.windows"}

        rule_tree = RuleTree()
        rule_tree.rule_parser = RuleParser(tag_map)

        rule = PreDetectorRule._create_from_dict(rule_dict)

        rule_tree.add_rule(rule)

        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay", "source": "foo"})
        assert not rule_tree.get_matching_rules({"winlog": "123", "test": "Okay", "windows": "foo"})
        assert rule_tree.get_matching_rules(
            {"winlog": "123", "test": "Okay", "source": {"windows": "foo"}}
        )

    def test_match_with_subrules(self, rule_dict):
        rule_tree = RuleTree()
        rule_dict["filter"] = "EventID: 1 AND winlog: 123"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)

        rule_dict["filter"] = "EventID: 1"
        subrule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(subrule)

        assert rule_tree.get_matching_rules({"EventID": "1", "winlog": "123"}) == [subrule, rule]

    def test_get_size(self, rule_dict):
        rule_tree = RuleTree()
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        assert rule_tree.get_size() == 2

        rule_dict["filter"] = "winlog: 123 AND xfoo: bar"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        assert rule_tree.get_size() == 4

        rule_dict["filter"] = "winlog: 123 AND xfoo: foo"
        rule = PreDetectorRule._create_from_dict(rule_dict)
        rule_tree.add_rule(rule)
        assert rule_tree.get_size() == 5

    def test_get_rules_as_list(self, rule_dict):
        rule_tree = RuleTree()

        rule_dict_2 = deepcopy(rule_dict)
        rule_dict_3 = deepcopy(rule_dict)

        rule_dict_2["filter"] = "winlog: 123 AND xfoo: bar"
        rule_dict_3["filter"] = "winlog: 123 AND xfoo: foo"

        rules = [
            PreDetectorRule._create_from_dict(rule_dict),
            PreDetectorRule._create_from_dict(rule_dict_2),
            PreDetectorRule._create_from_dict(rule_dict_3),
        ]
        _ = [rule_tree.add_rule(rule) for rule in rules]
        rules_from_rule_tree = rule_tree._get_rules_as_list()
        assert len(rules_from_rule_tree) == 3
        for rule in rules:
            assert rule in rules_from_rule_tree
