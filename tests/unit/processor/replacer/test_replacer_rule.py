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
                        "target_field": "test",
                        "mapping": {"test": "this is %{replace this}"},
                    },
                },
                TypeError,
                "unexpected keyword argument 'target_field'",
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
                "Replace once within string",
                "do %{replace this}!",
                ("do ", [["replace this", "!"]]),
            ),
            (
                "Replace once at beginning of string",
                "%{replace this}!",
                ("", [["replace this", "!"]]),
            ),
            (
                "Replace once at end of string",
                "do %{replace this}",
                ("do ", [["replace this", ""]]),
            ),
            (
                "Replace once whole string",
                "%{replace this}",
                ("", [["replace this", ""]]),
            ),
            (
                "Replace twice within string",
                "do %{replace} - %{this}!",
                ("do ", [["replace", " - "], ["this", "!"]]),
            ),
            (
                "Replace twice at beginning of string",
                "%{replace} - %{this}!",
                ("", [["replace", " - "], ["this", "!"]]),
            ),
            (
                "Replace twice at end of string",
                "do %{replace} - %{this}",
                ("do ", [["replace", " - "], ["this", ""]]),
            ),
            (
                "Replace twice whole string",
                "%{replace} - %{this}",
                ("", [["replace", " - "], ["this", ""]]),
            ),
            (
                "Replace nested takes first closing braces",
                "%{%{replace}}",
                ("", [["%{replace", "}"]]),
            ),
            (
                "Replace string with empty end",
                "String with variable ending%{}",
                ("String with variable ending", [["", ""]]),
            ),
            (
                "Replace string with wildcard at end",
                "String with variable ending%{*}",
                ("String with variable ending", [["*", "", True]]),
            ),
            (
                "Replace string with star at end",
                "String with variable ending%{\\*}",
                ("String with variable ending", [["*", "", False]]),
            ),
        ],
    )
    def test_get_template(self, testcase, template, expected):
        result = ReplacerRule._get_replacement_strings(template)
        replacements = []
        for replacement in expected[1]:
            if len(replacement) == 2:
                replacement.append(False)
            replacements.append(Replacement(*replacement))
        expected = ReplacementTemplate(expected[0], replacements)

        assert expected == result, testcase
