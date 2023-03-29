"""This module implements the tree node functionality for the tree model."""

from typing import Optional

from attrs import define, field

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.processor.base.rule import Rule


@define(slots=True)
class Node:
    """Tree node for rule tree model."""

    expression: FilterExpression

    children: list["Node", None] = field(factory=list, eq=False, repr=False, init=False)

    matching_rules: list[Rule] = field(factory=list, eq=False, repr=False)

    child_expressions: set[FilterExpression] = field(factory=set, eq=False, repr=False)

    @property
    def size(self) -> int:
        """returns size of the tree

        Returns
        -------
        int
            the size
        """
        if not self.children:
            return 1
        return sum((1, *(child.size for child in self.children)))  # pylint: disable=not-an-iterable

    @classmethod
    def from_rule(
        cls, rule: Rule, priority_dict: Optional[dict] = None, tag_map: Optional[dict] = None
    ) -> "Node":
        """creates node and additional nodes if needed add adds rule

        Parameters
        ----------
        rule : Rule
            the rule to add
        priority_dict : Optional[dict], optional
            a dict to prioritize, by default None
        tag_map : Optional[dict], optional
            to add special tags to expressions, by default None

        Returns
        -------
        Node
            the created node with subnodes and rules
        """
        priority_dict = {} if priority_dict is None else priority_dict
        tag_map = {} if tag_map is None else tag_map
        parsed_rule_filter_list = RuleParser.parse_rule(rule, priority_dict, tag_map)
        current_node = None
        for parsed_rule in parsed_rule_filter_list:
            for filter_expression in parsed_rule:
                node = Node(filter_expression, matching_rules=[rule])
                if current_node is None:
                    current_node = node
                current_node.add_child(node)
        return current_node

    def __hash__(self) -> int:
        return hash(repr(self))

    def add_child(self, node: "Node") -> bool:
        """Add child to node.

        This function adds a given child node to the node by appending it to the list of the node's
        children.

        Parameters
        ----------
        node: Node
            Child node to add to the node.

        """
        if self == node or node.expression in self.child_expressions:
            self.child_expressions |= node.child_expressions
            for child in self.children:  # pylint: disable=not-an-iterable
                success = child.add_child(node)
                if success:
                    return True
            self.child_expressions |= {node.expression}
            self.matching_rules += node.matching_rules
        if not self.children:
            self.children.append(node)
            self.matching_rules += node.matching_rules
            self.child_expressions |= node.child_expressions
        return False

    def add_rule(self, rule: Rule) -> None:
        """adds rule to node and creates subnodes if needed

        Parameters
        ----------
        rule : Rule
            the rule to add
        """
        node = Node.from_rule(rule)
        self.add_child(node)
