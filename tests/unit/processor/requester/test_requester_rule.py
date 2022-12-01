# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.requester.rule import RequesterRule


class TestRequesterRule:
    def test_create_from_dict_returns_requester_rule(self):
        rule = {
            "filter": "message",
            "requester": {"method": "GET", "url": "http://fancyapi"},
        }
        rule_dict = RequesterRule._create_from_dict(rule)
        assert isinstance(rule_dict, RequesterRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "requester": {"method": "GET", "url": "http://fancyapi"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "requester": {"kwargs": {}},
                },
                TypeError,
                "missing 2 required keyword-only arguments: 'method' and 'url'",
            ),
            (
                {
                    "filter": "message",
                    "requester": {},
                },
                TypeError,
                "missing 2 required keyword-only arguments: 'method' and 'url'",
            ),
            (
                {
                    "filter": "message",
                    "requester": {"method": "GET"},
                },
                TypeError,
                "missing 1 required keyword-only argument: 'url'",
            ),
            (
                {
                    "filter": "message",
                    "requester": {"method": "GET", "url": "bla"},
                },
                ValueError,
                "'url' must match regex",
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://the-api/endpoint",
                        "kwargs": {"notallowed": "bla"},
                    },
                },
                ValueError,
                r"'kwargs' must be in \['headers', 'files', 'data', 'params', 'auth', 'json'\]",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                RequesterRule._create_from_dict(rule)
        else:
            rule_instance = RequesterRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("requester").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)
