"""This module implements the rule parsing functionality.

Goal of this module is to parse each rule into a list of less complex rules with the same decision
behavior, allowing a simpler construction of the rule tree.

"""

from typing import TYPE_CHECKING

from logprep.filter.expression.filter_expression import (
    Always,
    Exists,
    Not,
)

from logprep.framework.rule_tree.demorgan_resolver import DeMorganResolver
from logprep.framework.rule_tree.rule_sorter import RuleSorter
from logprep.framework.rule_tree.rule_tagger import RuleTagger
from logprep.framework.rule_tree.rule_segmenter import RuleSegmenter

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule


class RuleParserException(Exception):
    """Raise if rule parser encounters a problem."""


class RuleParser:
    """Parse rule into list of less complex rules."""

    __slots__ = ("_demorgan_resolver", "_rule_segmenter", "_rule_tagger")

    _demorgan_resolver: DeMorganResolver
    _rule_segmenter: RuleSegmenter
    _rule_tagger: RuleTagger

    def __init__(self, tag_map: dict):
        """Initializes objects used for the rule parsing.

        Parameters
        ----------
        tag_map: dict
            Dictionary containing field names as keys and tags as values that is used to add special
            tags to the rule.

        """
        self._demorgan_resolver = DeMorganResolver()
        self._rule_segmenter = RuleSegmenter()
        self._rule_tagger = RuleTagger(tag_map)

    def parse_rule(self, rule: "Rule", priority_dict: dict) -> list:
        """Main parsing function to parse rule into list of less complex rules.

        This function aims to parse a rule into a list of less complex rules that shows the same
        decision behavior when matching events. The parsing process includes resolving NOT- and
        OR-expressions, sorting the expression segments of a rule as well as adding EXISTS-filter
        and special tags to the parsed rule.

        Parameters
        ----------
        rule: Rule
            Rule to be parsed.
        priority_dict: dict
            Dictionary containing priority values for field names that are used to sort filter
            expression in a rule.

        Returns
        -------
        list
            List of parsed rules. Each parsed rule is a list of filter expressions itself.
            The first list represents a disjunction and the sub-lists represent conjunctions,
            like in the disjunctive normal form.

        Raises
        ------
        RuleParserException
            Throws RuleParserException when parser encounters a problem during the parsing process.

        """
        filter_expression = self._demorgan_resolver.resolve(rule.filter)
        dnf_rule_segments = self._rule_segmenter.segment_into_dnf(rule, filter_expression)
        RuleSorter.sort_rule_segments(dnf_rule_segments, priority_dict)
        self._add_exists_filter(dnf_rule_segments)
        self._rule_tagger.add(dnf_rule_segments)

        return dnf_rule_segments

    @staticmethod
    def _add_exists_filter(parsed_rules: list):
        """Add Exists filter expression.

        In order to achieve better performances, this function adds Exists filter expression to
        the rule. E.g., before checking if a specific field "field" has values "a", "b" or "c" it
        checks if the given field even exists. Like this unnecessary comparisons can be prevented
        when the tree would check each of the values the field can have even when the field does
        not exist in the current event.

        Parameters
        ----------
        parsed_rules: list
            List of parsed rules. Each rule is a list of filter expressions.

        """
        for parsed_rule in parsed_rules:
            temp_parsed_rule = parsed_rule.copy()
            skipped_counter = 0

            for segment_index, segment in enumerate(temp_parsed_rule):
                if isinstance(segment, (Exists, Not, Always)):
                    skipped_counter += 1
                    continue

                exists_filter = Exists(segment.key)
                if exists_filter in parsed_rule:
                    skipped_counter += 1
                    continue

                parsed_rule.insert(segment_index * 2 - skipped_counter, exists_filter)
