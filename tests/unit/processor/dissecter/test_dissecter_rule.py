# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest
from logprep.processor.dissecter.rule import DissecterRule
from logprep.processor.base.exceptions import InvalidRuleDefinitionError


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
            DissecterRule._create_from_dict(rule)
