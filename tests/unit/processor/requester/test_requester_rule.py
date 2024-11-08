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
                    "filter": "domain",
                    "requester": {
                        "url": "https://internal.cmdb.local/api/v1/locations",
                        "method": "POST",
                        "target_field": "cmdb.location",
                        "headers": {"Authorization": "Bearer askdfjpiowejf283u9r"},
                        "json": {"hostname": "${message.hostname}"},
                    },
                    "description": "...",
                },
                None,
                None,
            ),
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
                    "requester": {"json": {}},
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
                        "headers": {"Authorization": "Bearer Bla"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://the-api/endpoint",
                        "headers": {"Authorization": {}},
                    },
                },
                TypeError,
                r"must be <class \'str\'>",
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "${field}",
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://the-api/endpoint",
                        "json": '{"key": "value"}',
                    },
                },
                TypeError,
                r"must be <class \\\'dict\\\'>",
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://the-api/endpoint",
                        "params": {"key": "value"},
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://the-api/endpoint",
                        "params": {"key": {}},
                    },
                },
                TypeError,
                r"must be <class \'str\'>",
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

    @pytest.mark.parametrize(
        "rule, expected_source_fields",
        [
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "${field1}",
                    },
                },
                ["field1"],
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                    },
                },
                ["field1", "field2"],
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                        "json": {"${jsonkey}": "the ${jsonvalue} bla"},
                    },
                },
                ["field1", "field2", "jsonkey", "jsonvalue"],
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                        "json": {"${jsonkey}": "the ${jsonvalue}"},
                    },
                },
                ["field1", "field2", "jsonkey", "jsonvalue"],
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                        "json": {"${jsonkey}": "the ${jsonvalue}"},
                        "params": {"${paramskey}": "the ${paramsvalue}"},
                        "data": "the data from field ${datafield.bla}",
                    },
                },
                [
                    "datafield.bla",
                    "field1",
                    "field2",
                    "jsonkey",
                    "jsonvalue",
                    "paramskey",
                    "paramsvalue",
                ],
            ),
        ],
    )
    def test_sets_source_fields(self, rule, expected_source_fields):
        rule_instance = RequesterRule._create_from_dict(rule)
        assert expected_source_fields == rule_instance.source_fields

    @pytest.mark.parametrize(
        "rule, expected_keys",
        [
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                        "json": {"${jsonkey}": "the ${jsonvalue}"},
                        "params": {"${paramskey}": "the ${paramsvalue}"},
                        "data": "the data from field ${datafield.bla}",
                    },
                },
                ["url", "json", "params", "data", "method", "timeout", "verify"],
            ),
            (
                {
                    "filter": "message",
                    "requester": {
                        "method": "GET",
                        "url": "http://${field1}/${field2}",
                    },
                },
                ["url", "method", "timeout", "verify"],
            ),
        ],
    )
    def test_kwargs_returns_requests_kwargs(self, rule, expected_keys):
        rule_instance = RequesterRule._create_from_dict(rule)
        assert sorted(expected_keys) == sorted(list(rule_instance.kwargs.keys()))
