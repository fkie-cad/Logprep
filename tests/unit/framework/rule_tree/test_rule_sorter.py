# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import (
    Not,
    Always,
    CompoundFilterExpression,
    StringFilterExpression,
    Exists,
)

from logprep.framework.rule_tree.rule_sorter import RuleSorter, RuleSorterException

pytest.importorskip("logprep.processor.pre_detector")

string_filter_expression_1 = StringFilterExpression(["key1"], "value1")
string_filter_expression_2 = StringFilterExpression(["key2"], "value2")
string_filter_expression_3 = StringFilterExpression(["key3"], "value3")
string_filter_expression_4 = StringFilterExpression(["key4"], "value4")

exists_expression_1 = Exists(["ABC.def"])
exists_expression_2 = Exists(["xyz"])


class TestRuleSorter:
    @pytest.mark.parametrize(
        "rule_list, priority_dict, expected",
        [
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_3,
                        string_filter_expression_2,
                    ]
                ],
                {},
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_2,
                        string_filter_expression_3,
                        string_filter_expression_4,
                    ]
                ],
            ),
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_3,
                        string_filter_expression_2,
                    ]
                ],
                {"key2": "1"},
                [
                    [
                        string_filter_expression_2,
                        string_filter_expression_1,
                        string_filter_expression_3,
                        string_filter_expression_4,
                    ]
                ],
            ),
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_3,
                        exists_expression_1,
                        string_filter_expression_2,
                        exists_expression_2,
                    ]
                ],
                {},
                [
                    [
                        exists_expression_1,
                        string_filter_expression_1,
                        string_filter_expression_2,
                        string_filter_expression_3,
                        exists_expression_2,
                    ]
                ],
            ),
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_3,
                        exists_expression_1,
                        string_filter_expression_2,
                        exists_expression_2,
                    ]
                ],
                {"xyz": "1"},
                [
                    [
                        exists_expression_2,
                        exists_expression_1,
                        string_filter_expression_1,
                        string_filter_expression_2,
                        string_filter_expression_3,
                    ]
                ],
            ),
            (
                [[string_filter_expression_2, Not(string_filter_expression_1)]],
                {"key1": "1"},
                [[Not(string_filter_expression_1), string_filter_expression_2]],
            ),
        ],
    )
    def test_sort_rule_segments(self, rule_list, priority_dict, expected):
        RuleSorter.sort_rule_segments(rule_list, priority_dict)
        assert rule_list == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            (Always("foo"), None),
            (Not(Always("foo")), None),
            (string_filter_expression_1, str(string_filter_expression_1)),
            (Not(string_filter_expression_1), str(string_filter_expression_1)),
            (Not(Not(string_filter_expression_1)), str(string_filter_expression_1)),
            (exists_expression_1, str(exists_expression_1)),
            (Not(exists_expression_1), str(exists_expression_1)),
        ],
    )
    def test_get_sorting_key_succeeds(self, expression, expected):
        assert RuleSorter._get_sorting_key(expression, {}) == expected

    @pytest.mark.parametrize(
        "expression",
        [CompoundFilterExpression(string_filter_expression_1, string_filter_expression_2), "foo"],
    )
    def test_get_sorting_key_raises_exception(self, expression):
        with pytest.raises(RuleSorterException, match=f'Could not sort "{str(expression)}"'):
            RuleSorter._get_sorting_key(expression, {})
