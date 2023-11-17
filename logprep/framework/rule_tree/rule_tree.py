"""This module contains the rule tree functionality."""

from enum import Enum
from logging import Logger
from typing import TYPE_CHECKING, List, Optional, Union

from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.util import getter

if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc.processor import Processor
    from logprep.processor.base.rule import Rule


class RuleTreeType(Enum):
    """Types of rule trees."""

    SPECIFIC = 1
    """Specific rule tree that is used to match specific rules."""
    GENERIC = 2
    """Generic rule tree that is used to match generic rules."""


class RuleTree:
    """Represent a set of rules using a rule tree model."""

    __slots__ = (
        "rule_parser",
        "priority_dict",
        "_rule_tree_type",
        "_rule_mapping",
        "_processor_config",
        "_processor_type",
        "_processor_name",
        "_root",
        "__dict__",
    )

    rule_parser: Optional[RuleParser]
    priority_dict: dict
    _rule_tree_type: Union[RuleTreeType, str]
    _rule_mapping: dict
    _processor_name: str
    _processor_config: "Processor.Config"
    _processor_type: str
    _root: Node

    def __init__(
        self,
        root: Node = None,
        processor_name: str = None,
        processor_config: "Processor.Config" = None,
        rule_tree_type: RuleTreeType = None,
    ):
        """Rule tree initialization function.

        Initializes a new rule tree with a given root node and a path to the tree's optional config
        file. If no root node is specified, a new node will be created and used as root node.
        Also starts the further setup.

        Parameters
        ----------
        root: Node, optional
            Node that should be used as the new rule tree's root node.
        processor_config: Processor.Config, optional
            Configuration of the processor that uses the rule tree.

        """
        self.rule_parser = None
        self._rule_mapping = {}
        self._processor_config = processor_config
        self._processor_name = processor_name if processor_name is not None else ""
        self._rule_tree_type = rule_tree_type.name.lower() if rule_tree_type is not None else ""
        self._processor_type = processor_config.type if processor_name is not None else ""
        self._setup()

        if root:
            self._root = root
        else:
            self._root = Node(None)

    @property
    def number_of_rules(self) -> int:
        return len(self._rule_mapping)

    def _setup(self):
        """Basic setup of rule tree.

        Initiate the rule tree's priority dict, tag map and load the configuration from file.

        """
        self.priority_dict = {}
        tag_map = {}

        if self._processor_config and self._processor_config.tree_config:
            config_data = getter.GetterFactory.from_string(
                self._processor_config.tree_config
            ).get_json()
            self.priority_dict = config_data["priority_dict"]
            tag_map = config_data["tag_map"]
        self.rule_parser = RuleParser(tag_map)

    def add_rule(self, rule: "Rule", logger: Logger = None):
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
        logger: Logger
            Logger to use for logging.

        """
        try:
            parsed_rule = self.rule_parser.parse_rule(rule, self.priority_dict)
        except Exception as error:  # pylint: disable=broad-except
            logger.warning(
                f'Error parsing rule "{rule.file_name}.yml": {type(error).__name__}: {error}. '
                f"Ignore and continue with next rule."
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

    def get_rule_id(self, rule: "Rule") -> int:
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
        return self._rule_mapping[rule]

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
