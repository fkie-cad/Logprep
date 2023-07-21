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
    StringFilterExpression,
)
from logprep.framework.rule_tree.demorgan_resolver import (
    DeMorganResolver,
    DeMorganResolverException,
)

string_filter_expression_1 = StringFilterExpression(["key1"], "value1")
string_filter_expression_2 = StringFilterExpression(["key2"], "value2")
string_filter_expression_3 = StringFilterExpression(["key3"], "value3")
string_filter_expression_4 = StringFilterExpression(["key4"], "value4")


@pytest.fixture(name="demorgan_resolver")
def fixture_demorgan_resolver():
    return DeMorganResolver()


class TestDeMorganResolver:
    @pytest.mark.parametrize(
        "expression, expected_resolved",
        [
            (string_filter_expression_1, string_filter_expression_1),
            (Not(string_filter_expression_1), Not(string_filter_expression_1)),
            (Not(And(Not(string_filter_expression_1))), Or(Not(Not(string_filter_expression_1)))),
            (
                Not(Or(string_filter_expression_1, string_filter_expression_2)),
                And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
            ),
            (
                Not(And(string_filter_expression_1, string_filter_expression_2)),
                Or(Not(string_filter_expression_1), Not(string_filter_expression_2)),
            ),
            (
                And(
                    Not(Or(string_filter_expression_1, string_filter_expression_2)),
                    string_filter_expression_3,
                ),
                And(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    string_filter_expression_3,
                ),
            ),
            (
                Or(
                    Not(Or(string_filter_expression_1, string_filter_expression_2)),
                    string_filter_expression_3,
                ),
                Or(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    string_filter_expression_3,
                ),
            ),
            (
                Not(
                    Or(
                        And(string_filter_expression_1, string_filter_expression_2),
                        string_filter_expression_3,
                    )
                ),
                And(
                    Or(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    Not(string_filter_expression_3),
                ),
            ),
            (
                Not(
                    And(
                        Or(string_filter_expression_1, string_filter_expression_2),
                        string_filter_expression_3,
                    )
                ),
                Or(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    Not(string_filter_expression_3),
                ),
            ),
            (
                And(
                    Not(And(string_filter_expression_1, string_filter_expression_2)),
                    string_filter_expression_3,
                ),
                And(
                    Or(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    string_filter_expression_3,
                ),
            ),
            (
                And(
                    Not(Or(string_filter_expression_1, string_filter_expression_2)),
                    Not(And(string_filter_expression_3, string_filter_expression_4)),
                ),
                And(
                    And(Not(string_filter_expression_1), Not(string_filter_expression_2)),
                    Or(Not(string_filter_expression_3), Not(string_filter_expression_4)),
                ),
            ),
        ],
    )
    def test_resolve(self, expression, expected_resolved, demorgan_resolver):
        assert demorgan_resolver.resolve(expression) == expected_resolved

    @pytest.mark.parametrize(
        "expression, expected_resolved, error",
        [
            (Not(string_filter_expression_1), Not(string_filter_expression_1), None),
            (
                string_filter_expression_1,
                string_filter_expression_1,
                (
                    DeMorganResolverException,
                    r'Can\'t resolve expression ".*", since it\'s not of the type "NOT."',
                ),
            ),
            (
                Not(
                    CompoundFilterExpression(string_filter_expression_1, string_filter_expression_2)
                ),
                Not(string_filter_expression_1),
                (
                    DeMorganResolverException,
                    r'Could not resolve expression ".*", '
                    + r'since its child is neither of the type "AND" nor "OR".',
                ),
            ),
        ],
    )
    def test_resolve_not_expression(self, expression, expected_resolved, error, demorgan_resolver):
        if error:
            with pytest.raises(error[0], match=error[1]):
                demorgan_resolver._resolve_not_expression(expression)
        else:
            assert demorgan_resolver._resolve_not_expression(expression) == expected_resolved
