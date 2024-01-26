# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.grokker.rule import GrokkerRule


class TestGrokkerRule:
    def test_create_from_dict_returns_grokker_rule(self):
        rule = {
            "filter": "message",
            "grokker": {"mapping": {"message": "Username: %{USER:user}"}},
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
                "Length of 'mapping' must be >= 1: 0",
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
                InvalidRuleDefinitionError,
                "no target fields defined",
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
                    "grokker": {"mapping": {"message": "this is a %{USER:field1}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:field.field1} some behind"}
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
                            "message": r"%{HOSTNAME:host} %{IP:client_ip} %{NUMBER:delay}s "
                            r"- \[%{DATA:time_stamp}\]"
                            r' "%{WORD:verb} %{URIPATHPARAM:uri_path} '
                            r'HTTP/%{NUMBER:http_ver}" %{INT:http_status} %{INT:bytes} %{QS}'
                            r" %{QS:client}"
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
            (
                {
                    "filter": "grok_me",
                    "grokker": {"mapping": {"grok_me": "%{GROK_PATTERN_DOES_NOT_EXISTS}"}},
                },
                ValueError,
                "grok pattern 'GROK_PATTERN_DOES_NOT_EXISTS' not found",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "(?<user>.*)"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "(?<user>.*) %{USER:user2}"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "%{USER:user2} some text within (?<user>.*)"}
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "grokker": {"mapping": {"message": "(?P<groupname>)"}},
                },
                ValueError,
                "must match regex",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "(?<group>(TOO(%{SPACE}(M(AN)Y)%{SPACE})PARENTHESES))"
                        }
                    },
                },
                InvalidRuleDefinitionError,
                r"The resolved grok pattern.*is not valid",
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {
                            "message": "(?<group>(NOT-TOO(%{SPACE}(MANY)%{SPACE})PARENTHESES))"
                        }
                    },
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                rule = GrokkerRule._create_from_dict(rule)
                rule.set_mapping_actions()
        else:
            rule_instance = GrokkerRule._create_from_dict(rule)
            rule_instance.set_mapping_actions()
            assert hasattr(rule_instance, "_config")
            for key, _ in rule.get("grokker").items():
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
                {"message": ["this is a %{USER:[user][username]}"]},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user.username}"},
                    },
                },
                {"message": ["this is a %{USER:[user][username]}"]},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user.username.firstname}"},
                    },
                },
                {"message": ["this is a %{USER:[user][username][firstname]}"]},
            ),
            (
                {
                    "filter": "message",
                    "grokker": {
                        "mapping": {"message": "this is a %{USER:user}"},
                    },
                },
                {"message": ["this is a %{USER:user}"]},
            ),
        ],
    )
    def test_ensure_dotted_field_notation_in_mapping(self, rule, expected_mapping):
        rule = GrokkerRule._create_from_dict(rule)
        assert rule._config.mapping == expected_mapping
