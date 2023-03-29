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
    """returns all children for this node"""

    matching_rules: list[Rule] = field(factory=list, eq=False, repr=False)
    """returns all rules for this node"""

    child_expressions: set[FilterExpression] = field(factory=set, eq=False, repr=False)
    """returns all expressions for child for faster lookup"""

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

    @property
    def is_root(self) -> bool:
        """returns True if self is root"""
        return self.expression == "root"

    @classmethod
    def from_rule(
        cls, rule: Rule, tree_config: Optional[dict] = None, tag_map: Optional[dict] = None
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
        tree_config = {} if tree_config is None else tree_config
        tag_map = {} if tag_map is None else tag_map
        parsed_rule_filter_list = RuleParser.parse_rule(rule, tree_config, tag_map)
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

    def add_child(self, node: "Node"):
        """Add child to node.

        This function adds a given child node to the node by appending it to the list of the node's
        children.

        Parameters
        ----------
        node: Node
            Child node to add to the node.

        """
        if self.is_root:
            for child in self.children:  # pylint: disable=not-an-iterable
                if node.expression in child.child_expressions:
                    child.add_child(node)
                    self.child_expressions |= {node.expression, *node.child_expressions}
        if self == node:
            for rule in node.matching_rules:
                if rule not in node.matching_rules:
                    self.matching_rules.append(rule)  # pylint: disable=no-member
            for node_child in node.children:
                self.add_child(node_child)
                self.child_expressions |= node_child.child_expressions
            self.child_expressions |= node.child_expressions
            return
        if node.expression in self.child_expressions:  # pylint: disable=unsupported-membership-test
            for own_child in self.children:  # pylint: disable=not-an-iterable
                if node == own_child or node.expression in own_child.child_expressions:
                    own_child.add_child(node)
                    self.child_expressions |= {node.expression}
                    return
        self.children.append(node)  # pylint: disable=no-member
        self.child_expressions |= {node.expression, *node.child_expressions}

    def add_rule(
        self, rule: Rule, tree_config: Optional[dict] = None, tag_map: Optional[dict] = None
    ) -> None:
        """adds rule to node and creates subnodes if needed

        Parameters
        ----------
        rule : Rule
            the rule to add
        """
        node = Node.from_rule(rule, tree_config, tag_map)
        self.add_child(node)

    def matches(self, event):
        """returns if node matches on incoming document"""
        return self.expression.matches(event)

    def get_matching_rules(self, event: dict) -> list["Rule"]:
        """Get all rules in the tree that match given event.
        This function gets all rules that were added to the rule tree that match a given event.
        When this function is called for the first time during the recursive matching process,
        the current node is assigned the tree root and the matching rules are initiated with an
        empty list. Subsequently, all children nodes of the current node are checked if they match
        the event. If a child node matches, all children of this child node are checked recursively.
        Also, if the matching child node has a matching rule, the matching rule is added to the
        matches.
        Parameters
        ----------
        event: dict
            Event dictionary that is used to check rules.
        Returns
        -------
        matches: list[Rule]
            Set of rules that match the given event.
        """
        matches = []
        matching_rules = self._retrieve_matching_rules(event, self, matches)
        matching_rules = list(dict.fromkeys(matching_rules))
        return matching_rules

    def _retrieve_matching_rules(
        self, event: dict, current_node: "Node" = None, matches: list["Rule"] = None
    ) -> list:
        """Recursively iterate through the rule tree to retrieve matching rules."""
        for child in current_node.children:
            if child.matches(event):
                current_node = child
                if current_node.matching_rules:
                    matches += child.matching_rules
                self._retrieve_matching_rules(event, current_node, matches)
        return matches
