# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logprep.filter.expression.filter_expression import StringFilterExpression
from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.processor.pre_detector.rule import PreDetectorRule


class TestNode:
    def test_init(self):
        expression = StringFilterExpression("foo", "bar")
        node = Node(expression)

        assert isinstance(node.expression, StringFilterExpression)
        assert node.expression == expression
        assert node.children == []

    def test_does_match_returns_true_as_expected(self):
        expression = StringFilterExpression("foo", "bar")
        node = Node(expression)

        event = {"foo": "bar"}

        assert node.expression.matches(event)

    def test_does_match_returns_false_as_expected(self):
        expression = StringFilterExpression("foo", "bar")
        node = Node(expression)

        event = {"bar": "foo"}

        assert not node.expression.matches(event)

    def test_add_child(self):
        expression_end = StringFilterExpression("foo", "bar")

        node_start = Node(None)
        node_end = Node(expression_end)

        node_start.add_child(node_end)

        assert node_start.children == [node_end]
        assert node_start.children[0].expression == expression_end
        node_start.add_child(node_end)
        assert node_start.children == [node_end]
        assert not node_end.children

    def test_expression_in_child_expressions(self):
        root = Node("root")
        root.add_child(Node(StringFilterExpression("foo", "bar")))
        assert isinstance(root.child_expressions, set)
        assert StringFilterExpression("foo", "bar") in root.child_expressions
        assert len(root.child_expressions) == 1
        root.add_child(Node(StringFilterExpression("foo", "bar")))
        assert StringFilterExpression("foo", "bar") in root.child_expressions
        assert len(root.child_expressions) == 1

    def test_get_child_with_expression(self):
        root = Node("root")
        root.add_child(Node(StringFilterExpression("foo", "bar")))
        root.add_child(Node(StringFilterExpression("foo", "bla")))

    def test_add_rule(self):
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
        parsed_rule_filter_list = RuleParser.parse_rule(rule, {}, {})
        node = Node(parsed_rule_filter_list)
        node.add_rule(parsed_rule_filter_list, rule)
