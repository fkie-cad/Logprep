# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import And, Or, Not, StringFilterExpression
from logprep.framework.rule_tree.rule_segmenter import RuleSegmenter, CnfToDnfConverter

string_filter_expression_1 = StringFilterExpression(["key1"], "value1")
string_filter_expression_2 = StringFilterExpression(["key2"], "value2")
string_filter_expression_3 = StringFilterExpression(["key3"], "value3")
string_filter_expression_4 = StringFilterExpression(["key4"], "value4")


class TestRuleSegmenter:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            (
                And(string_filter_expression_1, string_filter_expression_2),
                [string_filter_expression_1, string_filter_expression_2],
            ),
            (
                And(
                    string_filter_expression_1,
                    string_filter_expression_2,
                    string_filter_expression_3,
                ),
                [
                    string_filter_expression_1,
                    string_filter_expression_2,
                    string_filter_expression_3,
                ],
            ),
            (
                And(string_filter_expression_1, Not(string_filter_expression_2)),
                [string_filter_expression_1, Not(string_filter_expression_2)],
            ),
            (
                And(
                    string_filter_expression_1,
                    And(Not(string_filter_expression_2), string_filter_expression_3),
                ),
                [
                    string_filter_expression_1,
                    Not(string_filter_expression_2),
                    string_filter_expression_3,
                ],
            ),
        ],
    )
    def test_parse_and_expression(self, expression, expected):
        assert RuleSegmenter._segment_conjunctive_expression(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            (
                Or(string_filter_expression_1, string_filter_expression_2),
                [[string_filter_expression_1], [string_filter_expression_2]],
            ),
            (
                And(
                    string_filter_expression_1,
                    Or(string_filter_expression_2, string_filter_expression_3),
                ),
                [
                    [string_filter_expression_1, string_filter_expression_2],
                    [string_filter_expression_1, string_filter_expression_3],
                ],
            ),
            (
                And(
                    string_filter_expression_1,
                    Or(string_filter_expression_2, string_filter_expression_3),
                    string_filter_expression_4,
                ),
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_2,
                    ],
                    [
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_3,
                    ],
                ],
            ),
            (
                Or(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    string_filter_expression_3,
                ),
                [
                    [Not(string_filter_expression_1), Not(string_filter_expression_2)],
                    [string_filter_expression_3],
                ],
            ),
            (
                And(
                    Or(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    Not(string_filter_expression_3),
                ),
                [
                    [Not(string_filter_expression_3), Not(string_filter_expression_1)],
                    [Not(string_filter_expression_3), Not(string_filter_expression_2)],
                ],
            ),
            (
                And(
                    Not(string_filter_expression_1),
                    Not(string_filter_expression_2),
                    Or(Not(string_filter_expression_3), Not(string_filter_expression_4)),
                ),
                [
                    [
                        Not(string_filter_expression_1),
                        Not(string_filter_expression_2),
                        Not(string_filter_expression_3),
                    ],
                    [
                        Not(string_filter_expression_1),
                        Not(string_filter_expression_2),
                        Not(string_filter_expression_4),
                    ],
                ],
            ),
            (
                And(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    Or(Not(string_filter_expression_3), Not(string_filter_expression_4)),
                ),
                [
                    [
                        Not(string_filter_expression_2),
                        Not(string_filter_expression_1),
                        Not(string_filter_expression_3),
                    ],
                    [
                        Not(string_filter_expression_2),
                        Not(string_filter_expression_1),
                        Not(string_filter_expression_4),
                    ],
                ],
            ),
            (
                And(
                    Or(string_filter_expression_1, string_filter_expression_2),
                    Or(string_filter_expression_3, string_filter_expression_4),
                ),
                [
                    [string_filter_expression_1, string_filter_expression_3],
                    [string_filter_expression_1, string_filter_expression_4],
                    [string_filter_expression_2, string_filter_expression_3],
                    [string_filter_expression_2, string_filter_expression_4],
                ],
            ),
            (
                Or(
                    And(
                        string_filter_expression_1,
                        Or(string_filter_expression_2, string_filter_expression_3),
                    ),
                    string_filter_expression_4,
                ),
                [
                    [string_filter_expression_1, string_filter_expression_2],
                    [string_filter_expression_1, string_filter_expression_3],
                    [string_filter_expression_4],
                ],
            ),
        ],
    )
    def test_parse_or_expression(self, expression, expected):
        assert RuleSegmenter._segment_expression(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            (And(string_filter_expression_1, string_filter_expression_2), False),
            (Or(string_filter_expression_1, string_filter_expression_2), True),
            (Not(string_filter_expression_1), False),
            (Not(And(string_filter_expression_1, string_filter_expression_2)), False),
            (Not(Or(string_filter_expression_1, string_filter_expression_2)), True),
            (And(Not(Or(string_filter_expression_1, string_filter_expression_2))), True),
            (And(Not(And(string_filter_expression_1, string_filter_expression_2))), False),
        ],
    )
    def test_has_or_expression(self, expression, expected):
        assert RuleSegmenter._has_disjunction(expression) is expected

    @pytest.mark.parametrize(
        "expression_cnf, expected_dnf",
        [
            (
                [string_filter_expression_1, [[string_filter_expression_2]]],
                [[string_filter_expression_1, string_filter_expression_2]],
            ),
            (
                [[[string_filter_expression_1]], [[string_filter_expression_2]]],
                [[string_filter_expression_1, string_filter_expression_2]],
            ),
            (
                [
                    string_filter_expression_1,
                    [[string_filter_expression_2]],
                    string_filter_expression_3,
                ],
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_3,
                        string_filter_expression_2,
                    ]
                ],
            ),
            (
                [
                    string_filter_expression_1,
                    [[string_filter_expression_2], [string_filter_expression_3]],
                ],
                [
                    [string_filter_expression_1, string_filter_expression_2],
                    [string_filter_expression_1, string_filter_expression_3],
                ],
            ),
        ],
    )
    def test_convert_cnf_to_dnf(self, expression_cnf, expected_dnf):
        assert CnfToDnfConverter.convert_cnf_to_dnf(expression_cnf) == expected_dnf
