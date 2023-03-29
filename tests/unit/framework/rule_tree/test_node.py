# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=unsubscriptable-object
from logprep.filter.expression.filter_expression import Exists, StringFilterExpression
from logprep.framework.rule_tree.node import Node
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
        assert node_end.expression in node_start.child_expressions
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

    def test_from_rule_returns_node(self):
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
        node = Node.from_rule(rule)
        assert isinstance(node, Node)
        assert node.size == 2
        assert node.expression == Exists("winlog")
        assert node.children[0].size == 1
        assert node.children[0].expression == StringFilterExpression("winlog", "123")

    def test_adding_child_with_rule_to_node_results_in_one_additional_node(self):
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
        root_node = Node.from_rule(rule)
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 456",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        node = Node.from_rule(rule)
        assert root_node.add_child(node)
        assert root_node.size == 3

    def test_adding_child_with_rule_to_node_results_not_in_one_additional_node(self):
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
        root_node = Node.from_rule(rule)
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 456",
                "pre_detector": {
                    "id": 1,
                    "title": "1",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        node = Node.from_rule(rule)
        assert root_node.add_child(node)
        assert root_node.size == 3
        rule = PreDetectorRule._create_from_dict(
            {
                "filter": "winlog: 456",
                "pre_detector": {
                    "id": 1,
                    "title": "other title",
                    "severity": "0",
                    "case_condition": "directly",
                    "mitre": [],
                },
            }
        )
        node = Node.from_rule(rule)
        assert root_node.add_child(node)
        assert root_node.size == 3
