# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.replacer.rule import ReplacerRule, ReplacementTemplate, Replacement


class TestReplacerRule:
    def test_create_from_dict_returns_replacer_rule(self):
        rule = {
            "filter": "message",
            "replacer": {
                "mapping": {"test": "this is %{replace this}"},
            },
        }
        rule_dict = ReplacerRule.create_from_dict(rule)
        assert isinstance(rule_dict, ReplacerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this} and %{replace that}"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {},
                    },
                },
                ValueError,
                "Length of 'mapping' must be >= 1",
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "source_fields": ["test"],
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                TypeError,
                "unexpected keyword argument 'source_fields'",
            ),
            (
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "missing replacement pattern"},
                    },
                },
                ValueError,
                "'mapping' must match regex",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                ReplacerRule.create_from_dict(rule)
        else:
            rule_instance = ReplacerRule.create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("replacer").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "Two rules with same config",
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                True,
            ),
            (
                "Different filter",
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                {
                    "filter": "other-filter",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                False,
            ),
            (
                "Different mapping",
                {
                    "filter": "message",
                    "replacer": {
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                {
                    "filter": "other-filter",
                    "replacer": {
                        "mapping": {
                            "test": "this is %{replace this}",
                            "other": "this is %{replace this}",
                        },
                    },
                },
                False,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = ReplacerRule.create_from_dict(rule1)
        rule2 = ReplacerRule.create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase

    @pytest.mark.parametrize(
        ["testcase", "template", "expected"],
        [
            (
                "Do not replace",
                "do {not replace this}!",
                ("do {not replace this}!", []),
            ),
            (
                "Replace with colon notation",
                "do %{*:replace this}!",
                ("do ", [["replace this", "!", None, False, False]]),
            ),
            (
                "Replace with colon notation and empty replace value",
                "do %{*:}!",
                ("do ", [["", "!", None, False, False]]),
            ),
            (
                "Replace with colon notation and 1 backslash",
                "do %{*" + "\\" * 2 + ":replace this}!",
                ("do ", [["replace this", "!", "*" + "\\" * 1, False, False]]),
            ),
            (
                "Replace with colon notation and 2 backslashes",
                "do %{*" + "\\" * 4 + ":replace this}!",
                ("do ", [["replace this", "!", "*" + "\\" * 2, False, False]]),
            ),
            (
                "Replace with colon notation and 3 backslashes",
                "do %{*" + "\\" * 6 + ":replace this}!",
                ("do ", [["replace this", "!", "*" + "\\" * 3, False, False]]),
            ),
            (
                "Replace with colon notation escaped and no backslash",
                "do %{*\\:replace this}!",
                ("do ", [["*:replace this", "!", None, False, False]]),
            ),
            (
                "Replace with colon notation escaped and 1 backslash",
                "do %{*" + "\\" * 3 + ":replace this}!",
                ("do ", [["*" + "\\" * 1 + ":replace this", "!", None, False, False]]),
            ),
            (
                "Replace with colon notation escaped and 2 backslashes",
                "do %{*" + "\\" * 5 + ":replace this}!",
                ("do ", [["*" + "\\" * 2 + ":replace this", "!", None, False, False]]),
            ),
            (
                "Replace with colon notation escaped and 3 backslashes",
                "do %{*" + "\\" * 7 + ":replace this}!",
                ("do ", [["*" + "\\" * 3 + ":replace this", "!", None, False, False]]),
            ),
            (
                "Replace with escaped and not escaped colon",
                "do %{*\\:replace:this}!",
                ("do ", [["this", "!", "*:replace", False, False]]),
            ),
            (
                "Replace with not escaped and escaped colon",
                "%{*}-%{replace:this}%{*}!",
                (
                    "",
                    [
                        ["*", "-replace", None, True, False],
                        ["this", "", "replace", False, False],
                        ["*", "!", None, True, False],
                    ],
                ),
            ),
            (
                "Replace with not escaped and escaped colon",
                "do %{specifically:replace\\:this}!",
                ("do ", [["replace:this", "!", "specifically", False, False]]),
            ),
            (
                "Replace with escaped, not escaped and escaped colon",
                "do %{very\\:specifically:replace\\:this}!",
                ("do ", [["replace:this", "!", "very:specifically", False, False]]),
            ),
            (
                "Replace wildcard with colon notation",
                "do %{*:*}!",
                ("do ", [["*", "!", None, True, False]]),
            ),
            (
                "Replace escaped wildcard match with colon notation",
                "do %{\\*:*}!",
                ("do ", [["*", "!", "*", True, False]]),
            ),
            (
                "Replace escaped wildcard match with escaped wildcard in colon notation",
                "do %{\\*:\\*}!",
                ("do ", [["*", "!", "*", False, False]]),
            ),
            (
                "Replace double escaped wildcard match with colon notation",
                "do %{\\\\*:*}!",
                ("do ", [["*", "!", "\\*", True, False]]),
            ),
            (
                "Replace specific with colon notation",
                "do %{something:replace this}!",
                ("do ", [["replace this", "!", "something", False, False]]),
            ),
            (
                "Replace once within string",
                "do %{replace this}!",
                ("do ", [["replace this", "!", None, False, False]]),
            ),
            (
                "Replace once at beginning of string",
                "%{replace this}!",
                ("", [["replace this", "!", None, False, False]]),
            ),
            (
                "Replace once at end of string",
                "do %{replace this}",
                ("do ", [["replace this", "", None, False, False]]),
            ),
            (
                "Replace once whole string",
                "%{replace this}",
                ("", [["replace this", "", None, False, False]]),
            ),
            (
                "Replace twice within string",
                "do %{replace} - %{this}!",
                (
                    "do ",
                    [["replace", " - ", None, False, False], ["this", "!", None, False, False]],
                ),
            ),
            (
                "Replace twice at beginning of string",
                "%{replace} - %{this}!",
                ("", [["replace", " - ", None, False, False], ["this", "!", None, False, False]]),
            ),
            (
                "Replace twice at end of string",
                "do %{replace} - %{this}",
                ("do ", [["replace", " - ", None, False, False], ["this", "", None, False, False]]),
            ),
            (
                "Replace twice whole string",
                "%{replace} - %{this}",
                ("", [["replace", " - ", None, False, False], ["this", "", None, False, False]]),
            ),
            (
                "Replace greedily",
                "Do %{IP|g}.",
                ("Do ", [["IP", ".", None, False, True]]),
            ),
            (
                "Replace greedily escaped and no backslashes",
                "Do %{IP\\|g}.",
                ("Do ", [["IP|g", ".", None, False, False]]),
            ),
            (
                "Replace greedily with 1 backslash",
                "Do %{IP" + "\\" * 2 + "|g}.",
                ("Do ", [["IP" + "\\" * 1, ".", None, False, True]]),
            ),
            (
                "Replace greedily escaped and 1 backslash",
                "Do %{IP" + "\\" * 3 + "|g}.",
                ("Do ", [["IP" + "\\" * 1 + "|g", ".", None, False, False]]),
            ),
            (
                "Replace nested takes first closing braces",
                "%{%{replace}}",
                ("", [["%{replace", "}", None, False, False]]),
            ),
            (
                "Replace string with empty end",
                "String with variable ending%{}",
                ("String with variable ending", [["", "", None, False, False]]),
            ),
            (
                "Replace string with wildcard at end",
                "String with variable ending%{*}",
                ("String with variable ending", [["*", "", None, True, False]]),
            ),
            (
                "Replace string with star at end",
                "String with variable ending%{\\*}",
                ("String with variable ending", [["*", "", None, False, False]]),
            ),
        ],
    )
    def test_get_template(self, testcase, template, expected):
        result = ReplacerRule._get_replacement_strings(template)
        replacements = []
        for replacement in expected[1]:
            replacements.append(Replacement(*replacement))
        expected = ReplacementTemplate(expected[0], replacements)

        assert expected == result, testcase
