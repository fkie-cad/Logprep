# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.dissector.rule import DissectorRule, add_and_overwrite, append


class TestDissectorRule:

    rule = {"filter": "message", "dissector": {"mapping": {}}}

    def test_create_from_dict_returns_dissector_rule(self):
        dissector_rule = DissectorRule._create_from_dict(self.rule)
        assert isinstance(dissector_rule, DissectorRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {"filter": "message", "dissector": "I'm not a dict"},
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            ({"filter": "message", "dissector": {}}, None, None),
            (
                {"filter": "message", "dissector": {"mapping": {}}},
                None,
                None,
            ),
            (
                {"filter": "message", "dissector": {"convert_datatype": {}}},
                None,
                None,
            ),
            (
                {"filter": "message", "dissector": {"mapping": {"message": 2}}},
                TypeError,
                "expected string or bytes-like object",
            ),
            (
                {"filter": "message", "dissector": {"mapping": {1: "the message"}}},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {"filter": "message", "dissector": {"mapping": {1: ["invalid"]}}},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {
                        "mapping": {
                            "field": "%{ts} %{+ts} %{+ts} %{src} %{} %{prog}[%{pid}]: %{msg}"
                        }
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "invalid pattern"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{ts} "}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{%prog} %{pid}:%{msg}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{{prog} %{pid}:%{msg}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {"filter": "message", "dissector": {"convert_datatype": {"field1": "int"}}},
                None,
                None,
            ),
            (
                {"filter": "message", "dissector": {"convert_datatype": {"field1": "char"}}},
                ValueError,
                r"'convert_datatype' must be in \['float', 'int', 'string'\]",
            ),
            (
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{?prog} %{&pid}:%{msg}"}},
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                DissectorRule._create_from_dict(rule)
        else:
            dissector_rule = DissectorRule._create_from_dict(rule)
            assert hasattr(dissector_rule, "_config")
            for key, value in rule.get("dissector").items():
                assert hasattr(dissector_rule._config, key)
                assert value == getattr(dissector_rule._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "should be equal, because they are the same",
                {"filter": "message", "dissector": {}},
                {"filter": "message", "dissector": {}},
                True,
            ),
            (
                "should not be equal, because other filter",
                {"filter": "message", "dissector": {}},
                {"filter": "othermessage", "dissector": {}},
                False,
            ),
            (
                "should not be equal, because other field in mapping",
                {"filter": "message", "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}}},
                {
                    "filter": "message",
                    "dissector": {"mapping": {"other.field": "%{ts}:%{ts}:%{ts}"}},
                },
                False,
            ),
            (
                "should not be equal, because other dissect on same field in mapping",
                {"filter": "message", "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}}},
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{+ts}:%{ts}"}},
                },
                False,
            ),
            (
                "should not be equal, because other convert_datatype",
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissector": {
                        "convert_datatype": {"field": "int"},
                        "mapping": {"field": "%{ts}:%{ts}:%{ts}"},
                    },
                },
                False,
            ),
            (
                "should not be equal, because other convert_datatype and other field",
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissector": {
                        "convert_datatype": {"field": "int"},
                        "mapping": {"field1": "%{ts}:%{ts}:%{ts}"},
                    },
                },
                False,
            ),
            (
                "should not be equal, because other tag_on_failure",
                {
                    "filter": "message",
                    "dissector": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissector": {
                        "mapping": {"field1": "%{ts}:%{ts}:%{ts}"},
                        "tag_on_failure": ["_failed"],
                    },
                },
                False,
            ),
            (
                "should be equal, because same tag_on_failure",
                {
                    "filter": "message",
                    "dissector": {},
                },
                {
                    "filter": "message",
                    "dissector": {
                        "tag_on_failure": ["_dissector_failure"],
                    },
                },
                True,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = DissectorRule._create_from_dict(rule1)
        rule2 = DissectorRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase

    def test_converts_mappings_without_operator_to_add_field_to_action(self):
        rule = {
            "filter": "message",
            "dissector": {
                "mapping": {"field1": "%{field2}:%{field3} %{field4}"},
                "tag_on_failure": ["_failed"],
            },
        }
        dissector_rule = DissectorRule._create_from_dict(rule)
        assert dissector_rule.actions
        assert dissector_rule.actions[0] == ("field1", ":", "field2", add_and_overwrite, 0)
        assert dissector_rule.actions[1] == ("field1", " ", "field3", add_and_overwrite, 0)
        assert dissector_rule.actions[2] == ("field1", None, "field4", add_and_overwrite, 0)

    def test_converts_mappings_with_append_operator_to_append_field_to_action(self):
        rule = {
            "filter": "message",
            "dissector": {
                "mapping": {"field1": "%{field2}:%{+field3} %{field4}"},
                "tag_on_failure": ["_failed"],
            },
        }
        dissector_rule = DissectorRule._create_from_dict(rule)
        assert dissector_rule.actions
        assert dissector_rule.actions[0] == ("field1", ":", "field2", add_and_overwrite, 0)
        assert dissector_rule.actions[1] == ("field1", " ", "field3", append, 0)
        assert dissector_rule.actions[2] == ("field1", None, "field4", add_and_overwrite, 0)

    def test_converts_mappings_with_append_operator_and_order_modifier(self):
        rule = {
            "filter": "message",
            "dissector": {
                "mapping": {"field1": "%{field2}:%{+field3/1} %{+field4/3}"},
                "tag_on_failure": ["_failed"],
            },
        }
        dissector_rule = DissectorRule._create_from_dict(rule)
        assert dissector_rule.actions
        assert dissector_rule.actions[0] == ("field1", ":", "field2", add_and_overwrite, 0)
        assert dissector_rule.actions[1] == ("field1", " ", "field3", append, 1)
        assert dissector_rule.actions[2] == ("field1", None, "field4", append, 3)

    def test_adds_convert_actions(self):
        rule = {"filter": "message", "dissector": {"convert_datatype": {"field1": "int"}}}
        dissector_rule = DissectorRule._create_from_dict(rule)
        assert dissector_rule.convert_actions
        assert dissector_rule.convert_actions[0][0] == "field1"
        assert dissector_rule.convert_actions[0][1] == int

    def test_adds_multiple_convert_actions(self):
        rule = {
            "filter": "message",
            "dissector": {
                "convert_datatype": {
                    "field1": "int",
                    "other_field": "string",
                    "yet another field": "float",
                }
            },
        }
        dissector_rule = DissectorRule._create_from_dict(rule)
        assert dissector_rule.convert_actions
        assert dissector_rule.convert_actions[0][0] == "field1"
        assert dissector_rule.convert_actions[0][1] == int
        assert dissector_rule.convert_actions[1][0] == "other_field"
        assert dissector_rule.convert_actions[1][1] == str
        assert dissector_rule.convert_actions[2][0] == "yet another field"
        assert dissector_rule.convert_actions[2][1] == float
