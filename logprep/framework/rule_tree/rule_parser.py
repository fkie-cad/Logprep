"""This module implements the rule parsing functionality.

Goal of this module is to parse each rule into a list of less complex rules with the same decision
behavior, allowing a simpler construction of the rule tree.

"""

from typing import Union

from logprep.processor.base.rule import Rule
from logprep.filter.expression.filter_expression import (
    Or,
    CompoundFilterExpression,
    Not,
    And,
    Exists,
    StringFilterExpression,
    FilterExpression,
    Always,
)


class RuleParserException(Exception):
    """Raise if rule parser encounters a problem."""


class RuleParser:
    """Parse rule into list of less complex rules."""

    @staticmethod
    def parse_rule(rule: Rule, priority_dict: dict, tag_map: dict) -> list:
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
        tag_map: dict
            Dictionary containing field names as keys and tags as values that is used to add special
            tags to the rule.

        Returns
        -------
        parsed_rule_filter_list: list
            List of parsed rules. Each parsed rule is a list of filter expressions itself.

        Raises
        ------
        RuleParserException
            Throws RuleParserException when parser encounters a problem during the parsing process.

        """
        rule_filter = rule.filter
        rule_filter_parsed_not = RuleParser._parse_not_expression(rule_filter)

        if RuleParser._has_or_expression(rule_filter_parsed_not):
            parsed_rule_filter_list = RuleParser._parse_or_expression(rule_filter_parsed_not)
        elif isinstance(rule_filter_parsed_not, And):
            parsed_rule_filter_list = [RuleParser._parse_and_expression(rule_filter_parsed_not)]
        else:
            parsed_rule_filter_list = [[rule_filter_parsed_not]]

        if not parsed_rule_filter_list:
            raise RuleParserException("Rule probably not parsed correctly:", rule_filter)

        RuleParser._sort_rule_segments(parsed_rule_filter_list, priority_dict)
        RuleParser._add_exists_filter(parsed_rule_filter_list)
        RuleParser._add_special_tags(parsed_rule_filter_list, tag_map)

        return parsed_rule_filter_list

    @staticmethod
    def _parse_not_expression(
        rule: Union[Not, And, Or, StringFilterExpression]
    ) -> Union[Not, And, Or, StringFilterExpression]:
        """Parse NOT-expressions in given filter expression.

        This function resolves NOT-expressions found in the given filter expression according to
        De Morgan's Law.

        Parameters
        ----------
        rule: Union[Not, And, Or, StringFilterExpression]
            Given filter expression to be parsed.

        Returns
        -------
        result: Union[Not, And, Or, StringFilterExpression]
            Resulting filter expression created by resolving NOT-expressions in the given filter
            expression.

        """
        if RuleParser._has_unresolved_not_expression(rule):
            if isinstance(rule, Not):
                exp = rule.expression

                if isinstance(exp, StringFilterExpression):
                    return rule
                elif isinstance(exp, Or):
                    result_segments = ()

                    for or_segment in exp.expressions:
                        result_segments = result_segments + (Not(or_segment),)

                    result = And(*result_segments)

                    if RuleParser._has_unresolved_not_expression(result):
                        result = RuleParser._parse_not_expression(result)

                    return result
                elif isinstance(exp, And):
                    result_segments = ()

                    for and_segment in exp.expressions:
                        result_segments = result_segments + (Not(and_segment),)

                    result = Or(*result_segments)

                    if RuleParser._has_unresolved_not_expression(result):
                        result = RuleParser._parse_not_expression(result)

                    return result
            elif isinstance(rule, And):
                result_segments = ()

                for and_segment in rule.expressions:
                    result_segments = result_segments + (
                        RuleParser._parse_not_expression(and_segment),
                    )

                result = And(*result_segments)
                return result
            elif isinstance(rule, Or):
                result_segments = ()

                for or_segment in rule.expressions:
                    result_segments = result_segments + (
                        RuleParser._parse_not_expression(or_segment),
                    )

                result = Or(*result_segments)
                return result
        else:
            return rule

    @staticmethod
    def _has_unresolved_not_expression(rule: FilterExpression):
        """Check if given filter expression contains NOT-expressions.

        This function checks if the given filter expression contains any unresolved NOT-expressions.
        Simple NOT(field: value) expressions do not count as unresolved expression since it cannot
        be resolved.

        Parameters
        ----------
        rule: FilterExpression
            Filter expression to be checked for NOT-expressions.

        Returns
        -------
        has_unresolved_not_expression: bool
            Decision if given filter expression contains any unresolved NOT-expressions.

        """
        if isinstance(rule, Not):
            if isinstance(rule.expression, CompoundFilterExpression):
                return True
        elif isinstance(rule, CompoundFilterExpression):
            for expression in rule.expressions:
                if RuleParser._has_unresolved_not_expression(expression):
                    return True

    @staticmethod
    def _parse_or_expression(rule: FilterExpression) -> Union[list, tuple, FilterExpression]:
        """Parse filters with OR-expressions.

        This function parses filter expressions with OR-expressions recursively by splitting them
        into separate filter expressions using the distributive property of the logical operators
        AND and OR. During the recursive parsing process, different types are returned.
        Hence, different cases have to be handled when constructing the results.

        Parameters
        ----------
        rule: FilterExpression
            Filter expression with OR-expressions to be parsed.

        Returns
        -------
        result: Union[list, tuple, FilterExpression]
            Resulting filter expression created by resolving OR- and AND-expressions in the given
            filter expression. The return type may differ depending on the level of recursion.

        """
        if RuleParser._has_or_expression(rule):
            # If expression is OR-expression, parse it
            if isinstance(rule, Or):
                result_list = []

                for exp in rule.expressions:
                    # Recursively parse subexpressions of current expressions
                    loop_result = RuleParser._parse_or_expression(exp)

                    # Differentiate between different loop_result types and construct result_list accordingly
                    if not isinstance(loop_result, list):
                        if isinstance(loop_result, tuple):
                            loop_result = list(loop_result)
                        else:
                            loop_result = [loop_result]
                    if isinstance(loop_result, list) and isinstance(loop_result[0], list):
                        for element in loop_result:
                            result_list.append(element)
                    else:
                        result_list.append(loop_result)

                return result_list
            # Else, if expression is AND-expression, parse it and continue to parse OR-expression afterwards
            elif isinstance(rule, And):
                loop_results = []

                for exp in rule.expressions:
                    # Recursively parse subexpressions of current expressions
                    loop_results.append(RuleParser._parse_or_expression(exp))

                # Iterate through loop_results and resolve tuples
                for loop_result in loop_results:
                    if isinstance(loop_result, tuple):
                        tuple_segment = loop_result
                        loop_results.remove(tuple_segment)

                        for tuple_element in tuple_segment:
                            loop_results.insert(0, tuple_element)

                # Continue to parse OR-expressions in already parsed subexpressions
                return RuleParser._parse_or(loop_results)
        else:
            # Handle cases that may occur in recursive parsing process
            if isinstance(rule, And):
                return tuple(RuleParser._parse_and_expression(rule))
            else:
                return rule

    @staticmethod
    def _parse_or(loop_results: list):
        """Parse OR-expressions.

        This function handles the parsing of OR-subexpressions in AND-expression filters in a
        recursive manner.

        Parameters
        ----------
        loop_results: list
            List of filter expressions constructed during the parsing of AND-expressions that
            contain OR-expressions.

        Returns
        -------
        result_list: list
            Given input list with resolved OR-subexpressions.

        """
        result_list = []

        or_segment = RuleParser._pop_or_loop_result(loop_results)

        # Resolve OR expressions using distributive property
        for or_element in or_segment:
            result_list.append(loop_results + or_element)

        # Recursively resolve elements in result_list
        for parsed_rule in result_list.copy():
            for segment in parsed_rule:
                if isinstance(segment, list):
                    result_list.remove(parsed_rule)
                    rule_list = RuleParser._parse_or(parsed_rule)

                    for rule in rule_list:
                        result_list.append(rule)

        return result_list

    @staticmethod
    def _pop_or_loop_result(loop_results: list) -> list:
        """Pop element from list.

        This function iterates through the given list until it finds a list element that is a list
        itself, i.e. an OR-expression. The found element is then removed from the list and returned.

        Parameters
        ----------
        loop_results: list
            List of filter expressions to pop list from.

        Returns
        -------
        or_segment: list
            First element of given list that is a list itself, i.e. an OR-expression.

        """
        for loop_result in loop_results:
            if isinstance(loop_result, list):
                or_segment = loop_result
                loop_results.remove(or_segment)
                return or_segment
        return []

    @staticmethod
    def _has_or_expression(expression: FilterExpression) -> bool:
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
        elif isinstance(expression, CompoundFilterExpression):
            for exp in expression.expressions:
                if RuleParser._has_or_expression(exp):
                    return True

        if isinstance(expression, Not):
            return RuleParser._has_or_expression(expression.expression)

        return False

    @staticmethod
    def _sort_rule_segments(parsed_rule_list: list, priority_dict: dict):
        """Sort filter expressions in rule.

        This function sorts the filter expressions in all parsed rules without changing the rule's
        decision behavior.
        The expressions are sorted alphabetically or according to a defined priority dictionary.

        Goal of the sorting process is to achieve better processing times using the defined
        priorities and to minimize the resulting tree by ensuring an order in which fields to be
        checked occur in all rules.

        Parameters
        ----------
        parsed_rule_list: list
            List of parsed rules where every rule is a list of filter expressions.
        priority_dict: dict
            Dictionary with sorting priority information (key -> field name; value -> priority).

        """
        for parsed_rule in parsed_rule_list:
            parsed_rule.sort(key=lambda r: RuleParser._sort(r, priority_dict))

    @staticmethod
    def _sort(r: StringFilterExpression, priority_dict: dict) -> Union[dict, str]:
        """Helper function for _sort_rule_segments.

        This function is used by the _sort_rule_segments() function in the sorting key.
        It includes various cases to cover all the different expression classes. For every class it
        tries to get a priority value from the priority dict. If the field name used in the
        expression does not exist in the priority dict, the field name itself is returned to use an
        alphabetical sort.

        Parameters
        ----------
        r: StringFilterExpression
            Filter expression to get comparison value for.
        priority_dict: dict
            Dictionary with sorting priority information (key -> field name; value -> priority).

        Returns
        -------
        comparison_value: str
            Comparison value to use for sorting.

        """
        if isinstance(r, Always):
            return
        elif isinstance(r, Not):
            try:
                if isinstance(r.expression, Exists):
                    return priority_dict[r.expression._as_dotted_string(r.expression.split_field)]
                elif isinstance(r.expression, Not):
                    return priority_dict[r.expression.expression.split_field[0]]
                else:
                    return priority_dict[r._as_dotted_string(r.expression._key)]
            except KeyError:
                return RuleParser._sort(r.expression, priority_dict)
        elif isinstance(r, Exists):
            try:
                return priority_dict[r._as_dotted_string(r.split_field)]
            except KeyError:
                return r.__repr__()[1:-1]
        else:
            try:
                return priority_dict[r._as_dotted_string(r._key)]
            except KeyError:
                return r.__repr__()

    @staticmethod
    def _parse_and_expression(expression: FilterExpression) -> list:
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
            for segment in expression.expressions:
                if not isinstance(segment, And):
                    rule_list.append(segment)
                else:
                    looped_result = RuleParser._parse_and_expression(segment)

                    for s in looped_result:
                        rule_list.append(s)

        return rule_list

    @staticmethod
    def _add_special_tags(parsed_rules: list, tag_map: dict):
        """Add tags to rule filter.

        This function adds tags to the parsed rule filter. Tags are added according to a defined
        tag_map dictionary where the keys are field names and the values are filter expressions.

        If a field name defined in tag_map.keys() is found in a rule segment's filter expressions,
        the corresponding filter expression tag is created and added to the rule's segments as
        first segment.

        The idea behind tags is to improve a rule's processing time by checking the
        tag before processing the actual rule.

        Parameters
        ----------
        parsed_rules: list
            List containing parsed rules in a format where each rule consists of a list of filter
            expressions.
        tag_map: dict
            Dictionary containing field names as keys and tags as values that is used to add special
            tags to the rule.

        """

        if tag_map:
            for rule in parsed_rules:
                temp_rule = rule.copy()

                # Iterate through all segments and handle different cases
                for segment in temp_rule:
                    if isinstance(segment, Exists):
                        if segment.split_field[0] in tag_map.keys():
                            RuleParser._add_tag(rule, tag_map[segment.split_field[0]])
                    elif isinstance(segment, Not):
                        expression = segment.expression
                        if isinstance(expression, Exists):
                            if expression.split_field[0] in tag_map.keys():
                                RuleParser._add_tag(rule, tag_map[expression.split_field[0]])
                        elif expression._key[0] in tag_map.keys():
                            RuleParser._add_tag(rule, tag_map[expression._key[0]])
                    # Always Expressions do not need tags
                    elif isinstance(segment, Always):
                        continue
                    else:
                        if segment._key[0] in tag_map.keys():
                            RuleParser._add_tag(rule, tag_map[segment._key[0]])

    @staticmethod
    def _add_tag(rule, tag_map_value: str):
        """Add tag helper function.

        This function implements the functionality to add a tag for _add_special_tags().

        If the tag to add already exists, the function skips the new tag.
        Furthermore, it is distinguished between tags that create a simple Exists-filter expression
        and StringFilter-expressions (containing a ":").

        Parameters
        ----------
        rule: list
            List containing filter expressions representing the parsed rule.
        tag_map_value: str
            Value that is used to create the tag. If it contains a ":", a StringFilterExpression
            will be created.
            Else, an Exists-expression will be created.

        """
        if RuleParser._tag_exists(rule[0], tag_map_value):
            return

        if ":" in tag_map_value:
            key, value = tag_map_value.split(":")
            rule.insert(0, StringFilterExpression(key.split("."), value))
        else:
            rule.insert(0, Exists(tag_map_value.split(".")))

    @staticmethod
    def _tag_exists(segment, tag):
        """Helper function for _add_tag.

        Checks if the given segment is equal to the given tag.

        Parameters
        ----------
        segment: Union[Exists, StringFilterExpression]
            Segment to check if equal to tag.
        tag: str
            Tag to check for.

        Returns
        -------
        tag_exists: bool
            Decision if the given tag already exists as the given segment.

        """
        if isinstance(segment, Exists):
            if segment.__repr__()[1:-1] == tag:
                return True
        elif isinstance(segment, StringFilterExpression):
            if segment.__repr__().replace('"', "") == tag:
                return True

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

            for segment_index in range(len(temp_parsed_rule)):
                segment = temp_parsed_rule[segment_index]
                # Skip Always()-, Exists()- and Not()-expressions when adding Exists()-filter
                # Not()-expressions need to be skipped for cases where the field does not exist
                if (
                    not isinstance(segment, Exists)
                    and not isinstance(segment, Not)
                    and not isinstance(segment, Always)
                ):
                    exists_filter = Exists(segment._key)

                    # Skip if Exists()-filter already exists in Rule. No need to add it twice
                    if exists_filter in parsed_rule:
                        skipped_counter += 1
                    else:
                        # Insert Exists filter at the right place in the rule
                        parsed_rule.insert(segment_index * 2 - skipped_counter, exists_filter)
                else:
                    skipped_counter += 1
