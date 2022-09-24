# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest
from logprep.processor.dissecter.rule import DissecterRule
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.helper import add_field_to


class TestDissecterRule:

    rule = {"filter": "message", "dissecter": {"mapping": {}}}

    def test_create_from_dict_retuns_dissecter_rule(self):
        dissecter_rule = DissecterRule._create_from_dict(self.rule)
        assert isinstance(dissecter_rule, DissecterRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {"filter": "message", "dissecter": "I'm not a dict"},
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            ({"filter": "message", "dissecter": {}}, None, None),
            (
                {"filter": "message", "dissecter": {"mapping": {}}},
                None,
                None,
            ),
            (
                {"filter": "message", "dissecter": {"convert_datatype": {}}},
                None,
                None,
            ),
            (
                {"filter": "message", "dissecter": {"mapping": {"message": 2}}},
                TypeError,
                "expected string or bytes-like object",
            ),
            (
                {"filter": "message", "dissecter": {"mapping": {1: "the message"}}},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {"filter": "message", "dissecter": {"mapping": {1: ["invalid"]}}},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {
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
                    "dissecter": {"mapping": {"field": "invalid pattern"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}:"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}:%{ts} "}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{%prog} %{pid}:%{msg}"}},
                },
                ValueError,
                "must match regex",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                DissecterRule._create_from_dict(rule)
        else:
            dissecter_rule = DissecterRule._create_from_dict(rule)
            assert hasattr(dissecter_rule, "_config")
            for key, value in rule.get("dissecter").items():
                assert hasattr(dissecter_rule._config, key)
                assert value == getattr(dissecter_rule._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "should be equal, because they are the same",
                {"filter": "message", "dissecter": {}},
                {"filter": "message", "dissecter": {}},
                True,
            ),
            (
                "should not be equal, because other filter",
                {"filter": "message", "dissecter": {}},
                {"filter": "othermessage", "dissecter": {}},
                False,
            ),
            (
                "should not be equal, because other field in mapping",
                {"filter": "message", "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}}},
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"other.field": "%{ts}:%{ts}:%{ts}"}},
                },
                False,
            ),
            (
                "should not be equal, because other dissect on same field in mapping",
                {"filter": "message", "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}}},
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}:%{+ts}:%{ts}"}},
                },
                False,
            ),
            (
                "should not be equal, because other convert_datatype",
                {
                    "filter": "message",
                    "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissecter": {
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
                    "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissecter": {
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
                    "dissecter": {"mapping": {"field": "%{ts}:%{ts}:%{ts}"}},
                },
                {
                    "filter": "message",
                    "dissecter": {
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
                    "dissecter": {},
                },
                {
                    "filter": "message",
                    "dissecter": {
                        "tag_on_failure": ["_dissectfailure"],
                    },
                },
                True,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = DissecterRule._create_from_dict(rule1)
        rule2 = DissecterRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase

    def test_converts_mappings_without_operator_to_add_field_to_action(self):
        rule = {
            "filter": "message",
            "dissecter": {
                "mapping": {"field1": "%{field2}:%{field3} %{field4}"},
                "tag_on_failure": ["_failed"],
            },
        }
        dissecter_rule = DissecterRule._create_from_dict(rule)
        assert dissecter_rule.actions
        assert dissecter_rule.actions[0] == (":", "field2", add_field_to)
        assert dissecter_rule.actions[1] == (" ", "field3", add_field_to)
        assert dissecter_rule.actions[2] == (None, "field4", add_field_to)

    def test_converts_mappings_with_append_operator_to_append_field_to_action(self):
        rule = {
            "filter": "message",
            "dissecter": {
                "mapping": {"field1": "%{field2}:%{field3} %{field4}"},
                "tag_on_failure": ["_failed"],
            },
        }
        dissecter_rule = DissecterRule._create_from_dict(rule)
