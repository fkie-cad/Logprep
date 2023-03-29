"""This module contains the rule tree functionality."""

from functools import cached_property
from logging import Logger
from typing import TYPE_CHECKING, List

import numpy as np
from attr import Factory, define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.framework.rule_tree.node import Node
from logprep.metrics.metric import Metric

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule


@define(slots=True)
class RuleTree(Node):
    """Represent a set of rules using a rule tree model."""

    @define(kw_only=True)
    class RuleTreeMetrics(Metric):
        """Tracks statistics about the current rule tree"""

        number_of_rules: int = 0
        """Number of rules configured in the current rule tree"""
        rules: List["Rule.RuleMetrics"] = Factory(list)
        """List of rule metrics"""

        size: int = 0
        """Number of Nodes in the rule tree"""

        # pylint: disable=not-an-iterable
        # pylint: disable=protected-access
        @property
        def number_of_matches(self):
            """Sum of all rule matches"""
            return np.sum([rule._number_of_matches for rule in self.rules])

        @property
        def mean_processing_time(self):
            """Mean of all rule mean processing times"""
            times = [rule._mean_processing_time for rule in self.rules]
            if times:
                return np.mean(times)
            return 0.0

        # pylint: enable=not-an-iterable
        # pylint: enable=protected-access

    metric_labels: dict = field(
        eq=False,
        repr=False,
        default={"component": "rule_tree"},
        validator=validators.instance_of(dict),
    )
    expression: FilterExpression = field(default="root")
    tag_map: dict = field(
        eq=False, repr=False, factory=dict, validator=validators.instance_of(dict)
    )
    tree_config: dict = field(
        eq=False, repr=False, factory=dict, validator=validators.instance_of(dict)
    )

    metrics: RuleTreeMetrics = field(eq=False, repr=False, init=False, default=None)

    def __attrs_post_init__(self):
        self.metrics = self.RuleTreeMetrics(labels=self.metric_labels)

    def add_rule(self, rule: "Rule", logger: Logger = None):  # pylint: disable=arguments-differ
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
            super().add_rule(rule, self.tree_config, self.tag_map)
            self.metrics.number_of_rules += 1
            self.metrics.rules.append(rule.metrics)  # pylint: disable=no-member
        except Exception as ex:
            logger.warning(
                f'Error parsing rule "{rule.filter}": {type(ex).__name__}: {ex}.'
                f"\nIgnore and continue with next rule."
            )
            return

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
            current_node = self

        for child in current_node.children:
            print(
                "\t" * (depth - 1) + str(current_node.expression),
                "\t",
                "-" * depth + ">",
                child.expression,
                child.matching_rules,
            )

            self.print(child, depth + 1)
