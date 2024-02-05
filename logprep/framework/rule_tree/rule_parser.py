"""This module implements the rule parsing functionality.

Goal of this module is to parse each rule into a list of less complex rules with the same decision
behavior, allowing a simpler construction of the rule tree.

"""

from typing import TYPE_CHECKING

from logprep.abc.exceptions import LogprepException
from logprep.filter.expression.filter_expression import Always, Exists, Not
from logprep.framework.rule_tree.demorgan_resolver import DeMorganResolver
from logprep.framework.rule_tree.rule_segmenter import RuleSegmenter
from logprep.framework.rule_tree.rule_sorter import RuleSorter
from logprep.framework.rule_tree.rule_tagger import RuleTagger

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule


class RuleParserException(LogprepException):
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
        self._rule_tagger = RuleTagger(tag_map)

    def parse_rule(self, rule: "Rule", priority_dict: dict) -> list:
        """Main parsing function to parse rule into list of less complex rules.

        This function aims to parse a rule into a list of less complex rules that shows the same
        decision behavior when matching events.

        First, Not expressions are resolved by applying De Morgan's law on the rule's expression.
        Example: `not((A and not B) or not C)` becomes `(not A or B) and C`.

        Then the expression is transformed into a list representing the disjunctive normal form
        (DNF). This representation is required to build the rule tree.
        Example: `(not A or B) and C` becomes `[[not A, C], [B, C]]`,
        which is equivalent to the DNF `(not A and C) or (B and C)`.

        The segments are then sorted using a priority dict to achieve a better performance for
        rule matching.

        Afterwards, Exists filter expressions are added for every segment that is not an
        Exists, Not or Always expression.
        Those are then being checked first in the tree.
        Exists expressions are cheap and can lead to an optimization of the rule matching.

        Finally, tags may be added to more efficiently check the existence of configured fields.
        This is configured via a tag map, by specifying target fields and tags.
        Those tags are added as Exists filters in front of the rule to be checked first if the
        target field exists.
        Example: The tag map `{"some.key": "some_tag"}` would add an Exists filter
        `Exists("some_tag")` in front of the rules with filters `some.key: foo OR key_x` and
        `key_y AND some.key: bar`, but not the rule with filter `key_z: foo`, since it does not
        have the field `some.key`


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
        dnf_rule_segments = RuleSegmenter.segment_into_dnf(filter_expression)
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
            added_exists_filter_count = 0
            for segment_idx, segment in enumerate(temp_parsed_rule):
                if isinstance(segment, (Exists, Not, Always)):
                    continue

                exists_filter = Exists(segment.key)
                if exists_filter in parsed_rule:
                    continue
                parsed_rule.insert(segment_idx + added_exists_filter_count, exists_filter)
                added_exists_filter_count += 1
