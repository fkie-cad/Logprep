# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import Not

from logprep.framework.rule_tree.rule_sorter import RuleSorter
from tests.unit.framework.rule_tree.shared_constants import sfe_1, sfe_2, sfe_3, sfe_4, ex_1, ex_2

pytest.importorskip("logprep.processor.pre_detector")


class TestRuleSegmentSorter:
    @pytest.mark.parametrize(
        "rule_list, priority_dict, expected",
        [
            ([[sfe_1, sfe_4, sfe_3, sfe_2]], {}, [[sfe_1, sfe_2, sfe_3, sfe_4]]),
            ([[sfe_1, sfe_4, sfe_3, sfe_2]], {"key2": "1"}, [[sfe_2, sfe_1, sfe_3, sfe_4]]),
            ([[sfe_1, sfe_3, ex_1, sfe_2, ex_2]], {}, [[ex_1, sfe_1, sfe_2, sfe_3, ex_2]]),
            (
                [[sfe_1, sfe_3, ex_1, sfe_2, ex_2]],
                {"xyz": "1"},
                [[ex_2, ex_1, sfe_1, sfe_2, sfe_3]],
            ),
            ([[sfe_2, Not(sfe_1)]], {"key1": "1"}, [[Not(sfe_1), sfe_2]]),
        ],
    )
    def test_sort_rule_segments(self, rule_list, priority_dict, expected):
        RuleSorter.sort_rule_segments(rule_list, priority_dict)
        assert rule_list == expected
