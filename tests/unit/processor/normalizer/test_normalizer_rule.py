# pylint: disable=missing-docstring

import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.normalizer.rule import NormalizerRule


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": "message",
        "normalize": {
            "substitution_field": "foo",
            "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
            "timestamp_field": {
                "timestamp": {
                    "destination": "timestamp_field",
                    "source_formats": ["%Y %m %d - %H:%M:%S"],
                    "source_timezone": "UTC",
                    "destination_timezone": "Europe/Berlin",
                },
            },
        },
        "description": "insert a description text",
    }


class TestNormalizerRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other substitution_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "bar",
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of no substitution_field",
                {
                    "filter": "message",
                    "normalize": {
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of no grok_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other grok_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {"grok": ["%{IP:ip_bar} %{NUMBER:port_bar:int} bar"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of additional grok_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {
                            "grok": [
                                "%{IP:ip_foo} %{NUMBER:port_foo:int} foo",
                                "%{IP:ip_bar} %{NUMBER:port_bar:int} bar",
                            ]
                        },
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other timestamp_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                        "timestamp_field": {
                            "timestamp": {
                                "destination": "other_timestamp_field",
                                "source_formats": ["%Y %m %d - %H:%M:%S"],
                                "source_timezone": "UTC",
                                "destination_timezone": "Europe/Berlin",
                            },
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of no timestamp_field",
                {
                    "filter": "message",
                    "normalize": {
                        "substitution_field": "foo",
                        "grok_field": {"grok": ["%{IP:ip_foo} %{NUMBER:port_foo:int} foo"]},
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )
        rule2 = NormalizerRule(
            LuceneFilter.create(other_rule_definition["filter"]),
            other_rule_definition["normalize"],
        )
        assert (rule1 == rule2) == is_equal, testcase
