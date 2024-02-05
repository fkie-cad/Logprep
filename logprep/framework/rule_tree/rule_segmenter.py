"""This module implements functionality to segment expressions into simplified list expression."""

from typing import Union

from logprep.abc.exceptions import LogprepException
from logprep.filter.expression.filter_expression import (
    And,
    CompoundFilterExpression,
    FilterExpression,
    Not,
    Or,
)


class RuleSegmenterException(LogprepException):
    """Raise if rule segmenter encounters a problem."""


class RuleSegmenter:
    """Segments filter expression into list of less complex expressions.

    The segmenter gets a (compound) FilterExpression as input,
    which must have been already resolved via De Morgan's law.
    That means all NOT-expressions must have been resolved.
    The expression is then changed into the disjunctive normal form (DNF),
    which is required for the rule tree.
    However, the output is not another FilterExpression, but a list of lists with rule segments
    (FilterExpressions that are not compound), which represent the FilterExpression in DNF.
    The outer list representing OR and the inner lists representing AND.

    This representation then allows to easily sort the rule segments,
    add tags and build a tree out of them.

    Example:
    Assume the following CompoundFilterExpression X as input:

    `X := (A and (B or C)) or D`

    Furthermore, assume that A, B and C are StringFilterExpressions.

    Calling segment_into_dnf(X) would result in the list `[[A, B], [A, C], [D]]`.
    This is equivalent to the FilterExpression `(A and B) or (A and C) or (D)`,
    which is the DNF of X.

    """

    @staticmethod
    def segment_into_dnf(expression: FilterExpression) -> list:
        """Segment expression into list of less complex expressions."""
        if RuleSegmenter._has_disjunction(expression):
            rule_segments = RuleSegmenter._segment_expression(expression)
        elif isinstance(expression, And):
            rule_segments = [RuleSegmenter._segment_conjunctive_expression(expression)]
        else:
            rule_segments = [[expression]]
        return rule_segments

    @staticmethod
    def _has_disjunction(expression: FilterExpression) -> bool:
        """Check if given expression has OR-(sub)expression.

        This function checks if the given expression is an OR-expression or if any subexpression of
        the given expression is an OR-expression. Needed during recursive parsing processes.

        Parameters
        ----------
        expression: FilterExpression
            Given expression to check for OR-expression.

        Returns
        -------
        has_or_expression: bool
            Decision if given expression has OR-expression.

        """
        if isinstance(expression, Or):
            return True
        if isinstance(expression, CompoundFilterExpression):
            for exp in expression.children:
                if RuleSegmenter._has_disjunction(exp):
                    return True
        if isinstance(expression, Not):
            return RuleSegmenter._has_disjunction(expression.children[0])

        return False

    @staticmethod
    def _segment_expression(
        filter_expression: FilterExpression,
    ) -> Union[list, tuple, FilterExpression]:
        """Parse filters with OR-expressions.

        This function parses filter expressions with OR-expressions recursively by splitting them
        into separate filter expressions using the distributive property of the logical operators
        AND and OR. During the recursive parsing process, different types are returned.
        Hence, different cases have to be handled when constructing the results.

        Parameters
        ----------
        filter_expression: FilterExpression
            Filter expression with OR-expressions to be parsed.

        Returns
        -------
        result: Union[list, tuple, FilterExpression]
            Resulting filter expression created by resolving OR- and AND-expressions in the given
            filter expression. The return type may differ depending on the level of recursion.

        """
        if not RuleSegmenter._has_disjunction(filter_expression):
            # Handle cases that may occur in recursive parsing process
            if isinstance(filter_expression, And):
                return tuple(RuleSegmenter._segment_conjunctive_expression(filter_expression))
            return filter_expression
        if isinstance(filter_expression, Or):
            return RuleSegmenter._segment_disjunctive_expression(filter_expression)
        if isinstance(filter_expression, And):
            segmented_sub_expressions = RuleSegmenter._segment_sub_expressions(filter_expression)
            RuleSegmenter._flatten_tuples_in_list(segmented_sub_expressions)
            return CnfToDnfConverter.convert_cnf_to_dnf(segmented_sub_expressions)
        raise RuleSegmenterException(f"Could not segment {filter_expression}")

    @staticmethod
    def _segment_disjunctive_expression(filter_expression):
        result_list = []
        segmented_expression = RuleSegmenter._segment_sub_expressions(filter_expression)
        for expression in segmented_expression:
            expression_as_list = RuleSegmenter._convert_expression_to_list(expression)
            if all(isinstance(sub_expression, list) for sub_expression in expression_as_list):
                for sub_expression in expression_as_list:
                    result_list.append(sub_expression)
            else:
                result_list.append(expression_as_list)
        return result_list

    @staticmethod
    def _convert_expression_to_list(expression):
        if isinstance(expression, tuple):
            return list(expression)
        if not isinstance(expression, list):
            return [expression]
        return expression

    @staticmethod
    def _segment_sub_expressions(filter_expression: CompoundFilterExpression) -> list:
        """Recursively segment subexpressions of current expressions"""
        return [
            RuleSegmenter._segment_expression(expression)
            for expression in filter_expression.children
        ]

    @staticmethod
    def _flatten_tuples_in_list(expressions: list):
        """Iterate through sub_expressions and resolve tuples"""
        for expression in expressions:
            if isinstance(expression, tuple):
                expressions.remove(expression)  # pylint: disable=W4701
                for tuple_element in expression:
                    expressions.insert(0, tuple_element)

    @staticmethod
    def _segment_conjunctive_expression(expression: FilterExpression) -> list:
        """Parse AND-expression.

        This function parses AND-(sub)expressions in the given filter expression to a list of
        filter expressions.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to be parsed recursively.

        Returns
        -------
        rule_list: list
            List of filter expressions parsed from given filter expression.

        """
        rule_list = []

        if isinstance(expression, And):
            for segment in expression.children:
                if not isinstance(segment, And):
                    rule_list.append(segment)
                else:
                    for looped_segment in RuleSegmenter._segment_conjunctive_expression(segment):
                        rule_list.append(looped_segment)

        return rule_list


class CnfToDnfConverter:
    """Converts simplified rules from the conjunctive normal form to the disjunctive normal form"""

    @classmethod
    def convert_cnf_to_dnf(cls, cnf: list) -> list:
        """Convert rule from conjunctive normal form into disjunctive normal form.

        This function handles the parsing of OR-subexpressions in AND-expression filters in a
        recursive manner.
        It converts an input in conjunctive normal form into the disjunctive normal form.

        For the input the list represents a conjunction and the sub-lists represent disjunctions.
        For the output the list represents a disjunction and the sub-lists represent conjunctions.

        Parameters
        ----------
        cnf: list
            List of filter expressions constructed during the parsing of AND-expressions that
            contain OR-expressions.

        Returns
        -------
        result_list: list
            Given input list with resolved OR-subexpressions.

        Raises
        ------
        RuleSegmenterException
            Raises if converting the rule requires too much time, since the complexity of the
            transformation to the disjunctive normal form is exponential.

        """
        dnf = []
        or_segments = CnfToDnfConverter._pop_disjunctive_segment(cnf)
        CnfToDnfConverter._resolve_disjunctive_segment(or_segments, cnf, dnf)
        dnf_len = range(len(dnf))
        for idx in dnf_len:
            parsed_expression = dnf[idx]
            if any(isinstance(segment, list) for segment in parsed_expression):
                if parsed_expression in dnf:
                    dnf[idx] = None
                resolved_expressions = CnfToDnfConverter.convert_cnf_to_dnf(parsed_expression)

                for resolved_expression in resolved_expressions:
                    dnf.append(resolved_expression)
        dnf = [item for item in dnf if item is not None]
        return dnf

    @staticmethod
    def _pop_disjunctive_segment(expressions: list) -> list:
        """Pop OR-expression from list of expressions.

        This function iterates through the given list until it finds an OR-expression.
        That OR-expression is then removed from the list and returned.
        OR-expressions are represented as elements of the type list in the expressions list.

        Parameters
        ----------
        expressions: list
            List of filter expressions to pop list from.

        Returns
        -------
        or_segment: list
            First element of given list that is a list itself, i.e. an OR-expression.

        """
        for expression in expressions:
            if isinstance(expression, list):
                expressions.remove(expression)
                return expression
        return []

    @staticmethod
    def _resolve_disjunctive_segment(or_segment, expressions_in_cnf, expressions_in_dnf):
        """Resolve OR expressions using distributive property."""
        for or_element in or_segment:
            expressions_in_dnf.append(expressions_in_cnf + or_element)
