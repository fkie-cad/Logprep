# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import And, Or, Not
from logprep.framework.rule_tree.rule_segmenter import RuleSegmenter, CnfToDnfConverter
from tests.unit.framework.rule_tree.shared_constants import sfe_1, sfe_2, sfe_3, sfe_4


class TestRuleSegmenter:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            (And(sfe_1, sfe_2), [sfe_1, sfe_2]),
            (And(sfe_1, sfe_2, sfe_3), [sfe_1, sfe_2, sfe_3]),
            (And(sfe_1, Not(sfe_2)), [sfe_1, Not(sfe_2)]),
            (And(sfe_1, And(Not(sfe_2), sfe_3)), [sfe_1, Not(sfe_2), sfe_3]),
        ],
    )
    def test_parse_and_expression(self, expression, expected):
        assert RuleSegmenter._segment_conjunctive_expression(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            (Or(sfe_1, sfe_2), [[sfe_1], [sfe_2]]),
            (And(sfe_1, Or(sfe_2, sfe_3)), [[sfe_1, sfe_2], [sfe_1, sfe_3]]),
            (And(sfe_1, Or(sfe_2, sfe_3), sfe_4), [[sfe_1, sfe_4, sfe_2], [sfe_1, sfe_4, sfe_3]]),
            (Or(And(Not(sfe_1), Not(sfe_2)), sfe_3), [[Not(sfe_1), Not(sfe_2)], [sfe_3]]),
            (
                And(Or(Not(sfe_1), Not(sfe_2)), Not(sfe_3)),
                [[Not(sfe_3), Not(sfe_1)], [Not(sfe_3), Not(sfe_2)]],
            ),
            (
                And(Not(sfe_1), Not(sfe_2), Or(Not(sfe_3), Not(sfe_4))),
                [[Not(sfe_1), Not(sfe_2), Not(sfe_3)], [Not(sfe_1), Not(sfe_2), Not(sfe_4)]],
            ),
            (
                And(And(Not(sfe_1), Not(sfe_2)), Or(Not(sfe_3), Not(sfe_4))),
                [[Not(sfe_2), Not(sfe_1), Not(sfe_3)], [Not(sfe_2), Not(sfe_1), Not(sfe_4)]],
            ),
            (
                And(Or(sfe_1, sfe_2), Or(sfe_3, sfe_4)),
                [[sfe_1, sfe_3], [sfe_1, sfe_4], [sfe_2, sfe_3], [sfe_2, sfe_4]],
            ),
            (Or(And(sfe_1, Or(sfe_2, sfe_3)), sfe_4), [[sfe_1, sfe_2], [sfe_1, sfe_3], [sfe_4]]),
        ],
    )
    def test_parse_or_expression(self, expression, expected):
        assert RuleSegmenter._segment_expression(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            (And(sfe_1, sfe_2), False),
            (Or(sfe_1, sfe_2), True),
            (Not(sfe_1), False),
            (Not(And(sfe_1, sfe_2)), False),
            (Not(Or(sfe_1, sfe_2)), True),
            (And(Not(Or(sfe_1, sfe_2))), True),
            (And(Not(And(sfe_1, sfe_2))), False),
        ],
    )
    def test_has_or_expression(self, expression, expected):
        assert RuleSegmenter._has_disjunction(expression) is expected

    @pytest.mark.parametrize(
        "expression_cnf, expected_dnf",
        [
            ([sfe_1, [[sfe_2]]], [[sfe_1, sfe_2]]),
            ([[[sfe_1]], [[sfe_2]]], [[sfe_1, sfe_2]]),
            ([sfe_1, [[sfe_2]], sfe_3], [[sfe_1, sfe_3, sfe_2]]),
            ([sfe_1, [[sfe_2], [sfe_3]]], [[sfe_1, sfe_2], [sfe_1, sfe_3]]),
        ],
    )
    def test_convert_cnf_to_dnf(self, expression_cnf, expected_dnf):
        assert CnfToDnfConverter.convert_cnf_to_dnf(expression_cnf) == expected_dnf
