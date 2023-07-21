# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements

import pytest

from logprep.filter.expression.filter_expression import StringFilterExpression, Not, Exists
from logprep.framework.rule_tree.rule_tagger import RuleTagger

pytest.importorskip("logprep.processor.pre_detector")


string_filter_expression_1 = StringFilterExpression(["key1"], "value1")
string_filter_expression_2 = StringFilterExpression(["key2"], "value2")
string_filter_expression_3 = StringFilterExpression(["key3"], "value3")
string_filter_expression_4 = StringFilterExpression(["key4"], "value4")

exists_expression = Exists(["xyz"])


class TestRuleTagger:
    @pytest.mark.parametrize(
        "rule_list, tag_map, expected",
        [
            (
                [[string_filter_expression_1, string_filter_expression_2]],
                {"key2": "TAG"},
                [[Exists(["TAG"]), string_filter_expression_1, string_filter_expression_2]],
            ),
            (
                [
                    [string_filter_expression_1, string_filter_expression_2],
                    [string_filter_expression_1, string_filter_expression_3],
                ],
                {"key2": "TAG2", "key3": "TAG3"},
                [
                    [Exists(["TAG2"]), string_filter_expression_1, string_filter_expression_2],
                    [Exists(["TAG3"]), string_filter_expression_1, string_filter_expression_3],
                ],
            ),
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_2,
                    ],
                    [string_filter_expression_2, string_filter_expression_3],
                    [string_filter_expression_2],
                    [string_filter_expression_4, string_filter_expression_3],
                ],
                {"key1": "TAG1", "key2": "TAG2"},
                [
                    [
                        Exists(["TAG2"]),
                        Exists(["TAG1"]),
                        string_filter_expression_1,
                        string_filter_expression_4,
                        string_filter_expression_2,
                    ],
                    [Exists(["TAG2"]), string_filter_expression_2, string_filter_expression_3],
                    [Exists(["TAG2"]), string_filter_expression_2],
                    [string_filter_expression_4, string_filter_expression_3],
                ],
            ),
            (
                [
                    [string_filter_expression_1, string_filter_expression_3],
                    [string_filter_expression_2, string_filter_expression_4],
                ],
                {"key1": "TAG1", "key2": "TAG2.SUBTAG2"},
                [
                    [Exists(["TAG1"]), string_filter_expression_1, string_filter_expression_3],
                    [
                        Exists(["TAG2", "SUBTAG2"]),
                        string_filter_expression_2,
                        string_filter_expression_4,
                    ],
                ],
            ),
            (
                [
                    [string_filter_expression_1, string_filter_expression_3],
                    [string_filter_expression_2, string_filter_expression_4],
                ],
                {"key1": "TAG1:Value1", "key2": "TAG2.SUBTAG2"},
                [
                    [
                        StringFilterExpression(["TAG1"], "Value1"),
                        string_filter_expression_1,
                        string_filter_expression_3,
                    ],
                    [
                        Exists(["TAG2", "SUBTAG2"]),
                        string_filter_expression_2,
                        string_filter_expression_4,
                    ],
                ],
            ),
            (
                [
                    [string_filter_expression_1, string_filter_expression_3],
                    [string_filter_expression_2, string_filter_expression_4],
                ],
                {"key1": "TAG1.SUBTAG1:Value1", "key2": "TAG2.SUBTAG2"},
                [
                    [
                        StringFilterExpression(["TAG1", "SUBTAG1"], "Value1"),
                        string_filter_expression_1,
                        string_filter_expression_3,
                    ],
                    [
                        Exists(["TAG2", "SUBTAG2"]),
                        string_filter_expression_2,
                        string_filter_expression_4,
                    ],
                ],
            ),
            (
                [[string_filter_expression_1, exists_expression]],
                {"xyz": "TAG:VALUE"},
                [
                    [
                        StringFilterExpression(["TAG"], "VALUE"),
                        string_filter_expression_1,
                        exists_expression,
                    ]
                ],
            ),
            (
                [[Not(string_filter_expression_1)]],
                {"key1": "TAG"},
                [[Exists(["TAG"]), Not(string_filter_expression_1)]],
            ),
            (
                [[string_filter_expression_1]],
                {"key1": "key1:value1"},
                [[string_filter_expression_1]],
            ),
            (
                [[string_filter_expression_1, string_filter_expression_2, exists_expression]],
                {"key1": "TAG1", "key2": "xyz"},
                [
                    [
                        Exists(["TAG1"]),
                        string_filter_expression_1,
                        string_filter_expression_2,
                        exists_expression,
                    ]
                ],
            ),
            ([[string_filter_expression_1]], {}, [[string_filter_expression_1]]),
        ],
    )
    def test_add_special_tags(self, rule_list, tag_map, expected):
        rule_tagger = RuleTagger(tag_map)
        rule_tagger.add(rule_list)
        assert rule_list == expected

    @pytest.mark.parametrize(
        "expression, tag, tag_map, expected",
        [
            (exists_expression, "xyz", {"key1": "xyz"}, True),
            (exists_expression, "foo", {"key1": "foo"}, False),
            (string_filter_expression_1, "key1:value1", {"key1": "key1:value1"}, True),
            (string_filter_expression_1, "foo:bar", {"key1": "foo:bar"}, False),
        ],
    )
    def test_tag_exists(self, expression, tag, tag_map, expected):
        rule_tagger = RuleTagger(tag_map)
        assert rule_tagger._tag_exists(expression, tag) is expected
