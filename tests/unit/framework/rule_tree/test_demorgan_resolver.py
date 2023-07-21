# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import (
    And,
    Or,
    Not,
    CompoundFilterExpression,
)
from logprep.framework.rule_tree.demorgan_resolver import (
    DeMorganResolver,
    DeMorganResolverException,
)

from tests.unit.framework.rule_tree.shared_constants import sfe_1, sfe_2, sfe_3, sfe_4


@pytest.fixture(name="demorgan_resolver")
def fixture_demorgan_resolver():
    return DeMorganResolver()


class TestDeMorganResolver:
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
    def test_resolve(self, expression, resolved_expr, demorgan_resolver):
        assert demorgan_resolver.resolve(expression) == resolved_expr

    @pytest.mark.parametrize(
        "expression, resolved_expr, error",
        [
            (Not(sfe_1), Not(sfe_1), None),
            (
                sfe_1,
                sfe_1,
                (
                    DeMorganResolverException,
                    r'Can\'t resolve expression ".*", since it\'s not of the type "NOT."',
                ),
            ),
            (
                Not(CompoundFilterExpression(sfe_1, sfe_2)),
                Not(sfe_1),
                (
                    DeMorganResolverException,
                    r'Could not resolve expression ".*", '
                    + r'since its child is neither of the type "AND" nor "OR".',
                ),
            ),
        ],
    )
    def test_resolve_not_expression(self, expression, resolved_expr, error, demorgan_resolver):
        if error:
            with pytest.raises(error[0], match=error[1]):
                demorgan_resolver._resolve_not_expression(expression)
        else:
            assert demorgan_resolver._resolve_not_expression(expression) == resolved_expr
