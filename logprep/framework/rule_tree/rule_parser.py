from typing import Union

from logprep.processor.base.rule import Rule
from logprep.filter.expression.filter_expression import (Or, CompoundFilterExpression, Not, And, Exists,
                                                         StringFilterExpression, FilterExpression)


class RuleParserException(Exception):
    pass


class RuleParser:
    @staticmethod
    def parse_rule(rule: Rule, priority_dict: dict, tag_map: dict) -> list:
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
            rule: Union[Not, And, Or, StringFilterExpression]) -> Union[Not, And, Or, StringFilterExpression]:
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
                    result_segments = result_segments + (RuleParser._parse_not_expression(and_segment),)

                result = And(*result_segments)
                return result
            elif isinstance(rule, Or):
                result_segments = ()

                for or_segment in rule.expressions:
                    result_segments = result_segments + (RuleParser._parse_not_expression(or_segment),)

                result = Or(*result_segments)
                return result
        else:
            return rule

    @staticmethod
    def _has_unresolved_not_expression(rule: FilterExpression):
        if isinstance(rule, Not):
            if isinstance(rule.expression, CompoundFilterExpression):
                return True
        elif isinstance(rule, CompoundFilterExpression):
            for expression in rule.expressions:
                if RuleParser._has_unresolved_not_expression(expression):
                    return True

    @staticmethod
    def _parse_or_expression(rule: FilterExpression) -> Union[list, tuple, FilterExpression]:
        if RuleParser._has_or_expression(rule):
            if isinstance(rule, Or):
                result_list = []

                for exp in rule.expressions:
                    loop_result = RuleParser._parse_or_expression(exp)

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
            elif isinstance(rule, And):
                loop_results = []

                for exp in rule.expressions:
                    loop_results.append(RuleParser._parse_or_expression(exp))

                for loop_result in loop_results:
                    if isinstance(loop_result, tuple):
                        tuple_segment = loop_result
                        loop_results.remove(tuple_segment)

                        for tuple_element in tuple_segment:
                            loop_results.insert(0, tuple_element)

                return RuleParser._parse_or(loop_results)
        else:
            if isinstance(rule, And):
                return tuple(RuleParser._parse_and_expression(rule))
            else:
                return rule

    @staticmethod
    def _parse_or(loop_results: list):
        result_list = []

        or_segment = RuleParser._pop_or_loop_result(loop_results)

        for or_element in or_segment:
            result_list.append(loop_results + or_element)

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
        for loop_result in loop_results:
            if isinstance(loop_result, list):
                or_segment = loop_result
                loop_results.remove(or_segment)
                return or_segment
        return []

    @staticmethod
    def _has_or_expression(expression: FilterExpression) -> bool:
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
        for parsed_rule in parsed_rule_list:
            parsed_rule.sort(key=lambda r: RuleParser._sort(r, priority_dict))

    @staticmethod
    def _sort(r: StringFilterExpression, priority_dict: dict) -> Union[dict, str]:
        if isinstance(r, Not):
            try:
                if isinstance(r.expression, Exists):
                    return priority_dict[r.expression._as_dotted_string(r.expression.split_field)]
                elif isinstance(r.expression, Not):
                    return priority_dict[r.expression.expression.split_field[0]]
                else:
                    return priority_dict[r.expression._key[0]]
            except KeyError:
                return RuleParser._sort(r.expression, priority_dict)
        elif isinstance(r, Exists):
            try:
                return priority_dict[r._as_dotted_string(r.split_field)]
            except KeyError:
                return r.__repr__()[1:-1]
        else:
            try:
                return priority_dict[r._key[0]]
            except KeyError:
                return r.__repr__()

    @staticmethod
    def _parse_and_expression(expression: FilterExpression) -> list:
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
        if tag_map:
            for rule in parsed_rules:
                temp_rule = rule.copy()

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
                    else:
                        if segment._key[0] in tag_map.keys():
                            RuleParser._add_tag(rule, tag_map[segment._key[0]])

    @staticmethod
    def _add_tag(rule, tag_map_value: str):
        if RuleParser._tag_exists(rule[0], tag_map_value):
            return

        if ":" in tag_map_value:
            key, value = tag_map_value.split(":")
            rule.insert(0, StringFilterExpression(key.split("."), value))
        else:
            rule.insert(0, Exists(tag_map_value.split(".")))

    @staticmethod
    def _tag_exists(segment, tag):
        if isinstance(segment, Exists):
            if segment.__repr__()[1:-1] == tag:
                return True
        elif isinstance(segment, StringFilterExpression):
            if segment.__repr__().replace('"', '') == tag:
                return True

    @staticmethod
    def _add_exists_filter(parsed_rules: list):
        for parsed_rule in parsed_rules:
            temp_parsed_rule = parsed_rule.copy()
            skipped_counter = 0

            for segment_index in range(len(temp_parsed_rule)):
                segment = temp_parsed_rule[segment_index]
                # Skip Exists()-expression and Not()-expression when adding Exists()-filter
                # Not()-expressions need to be skipped for cases where the field does not exist
                if not isinstance(segment, Exists) and not isinstance(segment, Not):
                    exists_filter = Exists(segment._key)

                    # Skip if Exists()-filter already exists in Rule. No need to add it twice
                    if exists_filter in parsed_rule:
                        skipped_counter += 1
                    else:
                        parsed_rule.insert(segment_index * 2 - skipped_counter, exists_filter)
                else:
                    skipped_counter += 1
