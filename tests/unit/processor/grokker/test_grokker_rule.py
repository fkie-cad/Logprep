# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.grokker.rule import GrokkerRule


class TestGrokkerRule:
    def test_create_from_dict_returns_grokker_rule(self):
        rule = {
            "filter": "message",
            "grokker": {"mapping": {"message": "Username: %{USER}"}},
        }
        rule_dict = GrokkerRule._create_from_dict(rule)
        assert isinstance(rule_dict, GrokkerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {}},
                },
                ValueError,
                "'mapping' must be => 1",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "the message"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{USER}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{USER:field}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{USER:dotted.field}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{USER:dotted.field:int}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{USER:{dotted.field}}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{NUMBER:birthyear:int}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{NUMBER:birthday.year:int}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{NUMBER:[birthday][year]:int}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "{User}"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "this is a %{USER}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "this is a %{USER} some behind"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "this is a %{USER} some behind %{JAVASTACKTRACEPART}"
                        }
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "%{HOSTNAME:host} %{IP:client_ip} %{NUMBER:delay}s - \[%{DATA:time_stamp}\]"
                            ' "%{WORD:verb} %{URIPATHPARAM:uri_path} HTTP/%{NUMBER:http_ver}" %{INT:http_status} %{INT:bytes} %{QS}'
                            " %{QS:client}"
                        }
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "this is a %{USER} some behind %{JAVASTACKTRACEPART}"
                        },
                        "pattern_version": "legacy",
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "this is a %{USER} some behind %{JAVASTACKTRACEPART}"
                        },
                        "pattern_version": "ecs",
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "this is a %{USER} some behind %{JAVASTACKTRACEPART}"
                        },
                        "pattern_version": "nonsense",
                    },
                },
                ValueError,
                r"'pattern_version' must be in \('ecs', 'legacy'\)",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:[user][username]}"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "%{NUMBER:[birthday.year]:int}"}},
                },
                ValueError,
                "must match regex",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                GrokkerRule._create_from_dict(rule)
        else:
            rule_instance = GrokkerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("grokker").items():
                assert hasattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "should be equal, because they are the same",
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"field": "%{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"}
                    },
                },
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"field": "%{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"}
                    },
                },
                True,
            ),
            (
                "should not be equal, because other filter",
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"field": "%{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"}
                    },
                },
                {
                    "filter": "othermessage",
                    "grokker": {
                        "mapping": {"field": "%{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"}
                    },
                },
                False,
            ),
            (
                "should not be equal, because other field in mapping",
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"field": "%{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"}
                    },
                },
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "other.field": "{JAVASTACKTRACEPART}bla bla %{USER} bla %{HOSTNAME}"
                        }
                    },
                },
                False,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = GrokkerRule._create_from_dict(rule1)
        rule2 = GrokkerRule._create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase

    @pytest.mark.parametrize(
        "rule, expected_mapping",
        [
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:[user][username]}"},
                    },
                },
                {"message": "this is a %{USER:[user][username]}"},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user.username}"},
                    },
                },
                {"message": "this is a %{USER:[user][username]}"},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user.username.firstname}"},
                    },
                },
                {"message": "this is a %{USER:[user][username][firstname]}"},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user}"},
                    },
                },
                {"message": "this is a %{USER:user}"},
            ),
        ],
    )
    def test_ensure_dotted_field_notation_in_mapping(self, rule, expected_mapping):
        rule = GrokkerRule._create_from_dict(rule)
        assert rule._config.mapping == expected_mapping
