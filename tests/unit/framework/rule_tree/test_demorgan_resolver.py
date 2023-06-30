# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import And, Or, Not
from logprep.framework.rule_tree.demorgan_resolver import DeMorganResolver

from tests.unit.framework.rule_tree.shared_constants import sfe_1, sfe_2, sfe_3, sfe_4


@pytest.fixture(name="demorgan_resolver")
def fixture_demorgan_resolver():
    return DeMorganResolver()


class TestDeMorganResolver:
    @pytest.mark.parametrize(
        "expression, resolve_state",
        [
            (sfe_1, False),
            (Not(sfe_1), False),
            (And(sfe_1, sfe_2), False),
            (And(Not(sfe_1), sfe_2), False),
            (Or(And(sfe_1, Not(sfe_2))), False),
            (Or(And(sfe_1, sfe_2)), False),
            (Not(And(sfe_1, sfe_2)), True),
            (Or(Not(And(sfe_1, sfe_2)), sfe_3), True),
        ],
    )
    def test_has_unresolved_not_expression(self, expression, resolve_state, demorgan_resolver):
        assert demorgan_resolver._has_unresolved_expression(expression) == resolve_state

    @pytest.mark.parametrize(
        "expression, resolved_expr",
        [
            (sfe_1, sfe_1),
            (Not(sfe_1), Not(sfe_1)),
            (Not(And(Not(sfe_1))), Or(Not(Not(sfe_1)))),
            (Not(Or(sfe_1, sfe_2)), And(Not(sfe_1), Not(sfe_2))),
            (Not(And(sfe_1, sfe_2)), Or(Not(sfe_1), Not(sfe_2))),
            (And(Not(Or(sfe_1, sfe_2)), sfe_3), And(And(Not(sfe_1), Not(sfe_2)), sfe_3)),
            (Or(Not(Or(sfe_1, sfe_2)), sfe_3), Or(And(Not(sfe_1), Not(sfe_2)), sfe_3)),
            (Not(Or(And(sfe_1, sfe_2), sfe_3)), And(Or(Not(sfe_1), Not(sfe_2)), Not(sfe_3))),
            (Not(And(Or(sfe_1, sfe_2), sfe_3)), Or(And(Not(sfe_1), Not(sfe_2)), Not(sfe_3))),
            (And(Not(And(sfe_1, sfe_2)), sfe_3), And(Or(Not(sfe_1), Not(sfe_2)), sfe_3)),
            (
                And(Not(Or(sfe_1, sfe_2)), Not(And(sfe_3, sfe_4))),
                And(And(Not(sfe_1), Not(sfe_2)), Or(Not(sfe_3), Not(sfe_4))),
            ),
        ],
    )
    def test_resolve_not_expression(self, expression, resolved_expr, demorgan_resolver):
        assert demorgan_resolver.resolve(expression) == resolved_expr
