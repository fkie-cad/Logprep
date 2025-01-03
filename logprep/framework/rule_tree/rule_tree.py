"""
.. _Rule Tree:

RuleTree
========

For performance reasons on startup, all rules per processor are aggregated to a rule tree.
Instead of evaluating all rules independently for each log message, the message is checked against
the rule tree.
Each node in the rule tree represents a condition that has to be met,
while the leaves represent changes that the processor should apply.
If no condition is met, the processor will just pass the log event to the next processor.

.. _Rule Tree Configuration:

Rule Tree Configuration
^^^^^^^^^^^^^^^^^^^^^^^

To further improve the performance, it is possible to prioritize specific nodes of the rule tree,
such that broader conditions are higher up in the tree.
And specific conditions can be moved further down.
The following json gives an example of such a rule tree configuration.
This configuration will lead to the prioritization of `category` and `message` in the rule tree.

..  code-block:: json
    :linenos:

    {
      "priority_dict": {
        "category": "01",
        "message": "02"
      },
      "tag_map": {
        "check_field_name": "check-tag"
      }
    }

A path to a rule tree configuration can be set in any processor configuration under the key
:code:`tree_config`.
"""

from logging import getLogger
from typing import TYPE_CHECKING, List, Optional

from attrs import define, field, validators

from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.util import getter

if TYPE_CHECKING:  # pragma: no cover
    from logprep.processor.base.rule import Rule

logger = getLogger("RuleTree")


class RuleTree:
    """Represent a set of rules using a rule tree model."""

    @define(kw_only=True, slots=False)
    class Config:
        """Configuration for the RuleTree"""

        priority_dict: dict[str] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            default=dict(),
        )
        """Fields used in filter expressions can be prioritized by specifying
         them in this priority dict. The key describes the field name used in
         the filter expression and the value describes the priority in form
         of string number. The higher the number, the higher the priority."""

        tag_map: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            default=dict(),
        )
        """tbd"""

    __slots__ = (
        "rule_parser",
        "_rule_mapping",
        "tree_config",
        "_root",
        "__dict__",
    )

    tree_config: Config

    rule_parser: Optional[RuleParser]
    _rule_mapping: dict
    _root: Node

    def __init__(
        self,
        root: Node = None,
        config: str = None,
    ):
        """Rule tree initialization function.

        Initializes a new rule tree with a given root node and a path to the tree's optional config
        file. If no root node is specified, a new node will be created and used as root node.

        Parameters
        ----------
        root: Node, optional
            Node that should be used as the new rule tree's root node.
        config: str, optional
            Path to a tree configuration.
        """
        self._rule_mapping = {}
        self.tree_config = RuleTree.Config()
        if config:
            config_data = getter.GetterFactory.from_string(config).get_json()
            self.tree_config = RuleTree.Config(**config_data)
        self.rule_parser = RuleParser(self.tree_config.tag_map)

        self._root = Node(None)
        if root:
            self._root = root

    @property
    def number_of_rules(self) -> int:
        return len(self._rule_mapping)

    def add_rule(self, rule: "Rule"):
        """Add rule to rule tree.

        Add a new rule to the rule tree.
        The new rule is parsed into a list of "simple" rules with the same decision behavior
        before adding the parsed rules to the tree, e.g. by resolving OR-expressions.
        After adding a parsed rule, the new rule is added as matching rule to the last node of
        the corresponding parsed rule's subtree. Finally, the tree rule mapping is updated with the
        new rule and a unique ID.

        Parameters
        ----------
        rule: Rule
            Rule to be added to the rule tree.
        """
        try:
            parsed_rule = self.rule_parser.parse_rule(rule, self.tree_config.priority_dict)
        except Exception as error:  # pylint: disable=broad-except
            logger.warning(
                'Error parsing rule "%s.yml": %s: %s. Ignore and continue with next rule.',
                rule.file_name,
                type(error).__name__,
                error,
            )
            return
        for rule_segment in parsed_rule:
            end_node = self._add_parsed_rule(rule_segment)
            if rule not in end_node.matching_rules:
                end_node.matching_rules.append(rule)
        self._rule_mapping[rule] = self.number_of_rules

    def _add_parsed_rule(self, parsed_rule: list):
        """Add parsed rule to rule tree.

        This function adds a parsed sub-rule of a given rule to the rule tree by iterating through
        the current tree.

        For every filter expression in the parsed rule, the children of the current node are
        checked for the expression. If the current node has a child with such a filter expression,
        the function continues with this child. Else, a new node is created with the current filter
        expression and is added to the current node's children.

        Parameters
        ----------
        parsed_rule: list
            Parsed rule in form of a list of filter expressions.

        Returns
        -------
        current_node: Node
            The last node that was added to the rule tree for the current parsed rule.

        """
        current_node = self.root

        for expression in parsed_rule:
            child_with_expression = current_node.get_child_with_expression(expression)
            if child_with_expression:
                current_node = child_with_expression
            else:
                new_node = Node(expression)
                current_node.add_child(new_node)
                current_node = new_node

        return current_node

    def get_rule_id(self, rule: "Rule") -> Optional[int]:
        """Returns ID of given rule.

        This function returns the ID of a given rule. It is used by the processors to get the ID of
        a matching rule in the tree when generating processing stats.

        Parameters
        ----------
        rule: Rule
            Rule to get ID from.

        Returns
        -------
        rule_id: int
            The rule's ID.

        """
        return self._rule_mapping.get(rule)

    def get_matching_rules(self, event: dict) -> List["Rule"]:
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
        matches: List[Rule]
            Set of rules that match the given event.
        """
        matches = []
        matching_rules = self._retrieve_matching_rules(event, self.root, matches)
        matching_rules = list(dict.fromkeys(matching_rules))
        return matching_rules

    def _retrieve_matching_rules(
        self, event: dict, current_node: Node = None, matches: List["Rule"] = None
    ) -> list:
        """Recursively iterate through the rule tree to retrieve matching rules."""
        for child in current_node.children:
            if child.does_match(event):
                current_node = child
                if current_node.matching_rules:
                    matches += child.matching_rules
                self._retrieve_matching_rules(event, current_node, matches)
        return matches

    def print(self, current_node: Node = None, depth: int = 1):
        """Print rule tree to console.

        This function prints the current rule tree with its nodes and transitions to the console
        recursively. When it is called for the first time, the current node is initiated with the
        tree's root node.

        Parameters
        ----------
        current_node: Node
            Tree node that is currently looked at in the recursive printing process.
        depth: int
            Current depth in the rule tree used for prettier prints.

        """
        if not current_node:
            current_node = self._root

        for child in current_node.children:
            indentations = "\t" * (depth - 1)
            arrow_length = "-" * depth
            print(
                f"{indentations}{current_node.expression} \t {arrow_length}> "
                f"{child.expression} {child.matching_rules}"
            )
            self.print(child, depth + 1)

    def get_size(self, current_node: Node = None) -> int:
        """Get size of tree.

        Count all nodes in the rule tree by recursively iterating through it and return the result.

        Parameters
        ----------
        current_node: Node
            Tree node that is currently looked at in the recursive counting process.

        Returns
        -------
        size: int
            Size of the rule tree, i.e. the number of nodes in it.

        """
        if not current_node:
            current_node = self._root

        size = 0
        size += len(current_node.children)

        for child in current_node.children:
            size += self.get_size(child)

        return size

    def _get_rules_as_list(self) -> List["Rule"]:
        """get all rules
        Returns
        -------
        rules: List[Rule]

        """

        return list(self._rule_mapping)

    @property
    def rules(self):  # pylint: disable=missing-docstring
        return self._get_rules_as_list()

    @property
    def root(self) -> Node:  # pylint: disable=missing-docstring
        return self._root
