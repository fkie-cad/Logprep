from logprep.filter.expression.filter_expression import StringFilterExpression
from logprep.framework.rule_tree.node import Node


class TestNode:
    def test_init(self):
        expression = StringFilterExpression("foo", "bar")
        node = Node(expression)

        assert isinstance(node.expression, StringFilterExpression)
        assert node.expression == expression
        assert node.children == []

    def test_does_match_returns_true_as_expected(self):
        expression = StringFilterExpression(["foo"], "bar")
        node = Node(expression)

        event = {"foo": "bar"}

        assert node.does_match(event)

    def test_does_match_returns_false_as_expected(self):
        expression = StringFilterExpression(["foo"], "bar")
        node = Node(expression)

        event = {"bar": "foo"}

        assert not node.does_match(event)

    def test_add_child(self):
        expression_end = StringFilterExpression(["foo"], "bar")

        node_start = Node(None)
        node_end = Node(expression_end)

        node_start.add_child(node_end)

        assert node_start.children == [node_end]
        assert node_start.children[0].expression == expression_end

    def test_has_child_with_expression(self):
        expression_end = StringFilterExpression("foo", "bar")

        node_start = Node(None)
        node_end = Node(expression_end)

        node_start.add_child(node_end)

        assert node_start.has_child_with_expression(StringFilterExpression("foo", "bar"))
        assert not node_start.has_child_with_expression(StringFilterExpression("foooo", "baaar"))

    def test_get_child_with_expression(self):
        expression_end = StringFilterExpression("foo", "bar")

        node_start = Node(None)
        node_end = Node(expression_end)

        node_start.add_child(node_end)

        assert node_start.get_child_with_expression(expression_end) == node_end
