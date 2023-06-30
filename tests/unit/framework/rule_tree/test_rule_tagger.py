# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import StringFilterExpression, Not, Exists
from logprep.framework.rule_tree.rule_tagger import RuleTagger
from tests.unit.framework.rule_tree.shared_constants import sfe_1, sfe_2, sfe_3, sfe_4, ex_2

pytest.importorskip("logprep.processor.pre_detector")


class TestRuleTagger:
    @pytest.mark.parametrize(
        "rule_list, tag_map, expected",
        [
            ([[sfe_1, sfe_2]], {"key2": "TAG"}, [[Exists(["TAG"]), sfe_1, sfe_2]]),
            (
                [[sfe_1, sfe_2], [sfe_1, sfe_3]],
                {"key2": "TAG2", "key3": "TAG3"},
                [[Exists(["TAG2"]), sfe_1, sfe_2], [Exists(["TAG3"]), sfe_1, sfe_3]],
            ),
            (
                [[sfe_1, sfe_4, sfe_2], [sfe_2, sfe_3], [sfe_2], [sfe_4, sfe_3]],
                {"key1": "TAG1", "key2": "TAG2"},
                [
                    [Exists(["TAG2"]), Exists(["TAG1"]), sfe_1, sfe_4, sfe_2],
                    [Exists(["TAG2"]), sfe_2, sfe_3],
                    [Exists(["TAG2"]), sfe_2],
                    [sfe_4, sfe_3],
                ],
            ),
            (
                [[sfe_1, sfe_3], [sfe_2, sfe_4]],
                {"key1": "TAG1", "key2": "TAG2.SUBTAG2"},
                [
                    [Exists(["TAG1"]), sfe_1, sfe_3],
                    [Exists(["TAG2", "SUBTAG2"]), sfe_2, sfe_4],
                ],
            ),
            (
                [[sfe_1, sfe_3], [sfe_2, sfe_4]],
                {"key1": "TAG1:Value1", "key2": "TAG2.SUBTAG2"},
                [
                    [StringFilterExpression(["TAG1"], "Value1"), sfe_1, sfe_3],
                    [Exists(["TAG2", "SUBTAG2"]), sfe_2, sfe_4],
                ],
            ),
            (
                [[sfe_1, sfe_3], [sfe_2, sfe_4]],
                {"key1": "TAG1.SUBTAG1:Value1", "key2": "TAG2.SUBTAG2"},
                [
                    [StringFilterExpression(["TAG1", "SUBTAG1"], "Value1"), sfe_1, sfe_3],
                    [Exists(["TAG2", "SUBTAG2"]), sfe_2, sfe_4],
                ],
            ),
            (
                [[sfe_1, ex_2]],
                {"xyz": "TAG:VALUE"},
                [[StringFilterExpression(["TAG"], "VALUE"), sfe_1, ex_2]],
            ),
            ([[Not(sfe_1)]], {"key1": "TAG"}, [[Exists(["TAG"]), Not(sfe_1)]]),
            ([[sfe_1]], {"key1": "key1:value1"}, [[sfe_1]]),
            (
                [[sfe_1, sfe_2, ex_2]],
                {"key1": "TAG1", "key2": "xyz"},
                [[Exists(["TAG1"]), sfe_1, sfe_2, ex_2]],
            ),
            ([[sfe_1]], {}, [[sfe_1]]),
        ],
    )
    def test_add_special_tags(self, rule_list, tag_map, expected):
        rule_tagger = RuleTagger(tag_map)
        rule_tagger.add(rule_list)
        assert rule_list == expected

    @pytest.mark.parametrize(
        "expression, tag, tag_map, expected",
        [
            (ex_2, "xyz", {"key1": "xyz"}, True),
            (ex_2, "foo", {"key1": "foo"}, False),
            (sfe_1, "key1:value1", {"key1": "key1:value1"}, True),
            (sfe_1, "foo:bar", {"key1": "foo:bar"}, False),
        ],
    )
    def test_tag_exists(self, expression, tag, tag_map, expected):
        rule_tagger = RuleTagger(tag_map)
        assert rule_tagger._tag_exists(expression, tag) is expected
