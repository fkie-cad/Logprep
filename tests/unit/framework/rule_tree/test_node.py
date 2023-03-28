from logprep.filter.expression.filter_expression import StringFilterExpression
from logprep.framework.rule_tree.node import Node


class TestNode:
    def test_init(self):
        expression = StringFilterExpression("foo", "bar")
        node = Node(expression)

        assert isinstance(node.expression, StringFilterExpression)
        assert node.expression == expression
        assert node.children == {}

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

        assert node_start.children == {node_end: None}
        assert node_start.children.popitem()[0].expression == expression_end
