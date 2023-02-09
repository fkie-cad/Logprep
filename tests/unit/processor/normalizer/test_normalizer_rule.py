# pylint: disable=missing-docstring
# pylint: disable=protected-access

import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.normalizer.rule import NormalizerRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
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

    def test_grok_loads_one_pattern(self):
        grok_rule = {
            "filter": "message",
            "normalize": {
                "some_grok_field": {"grok": "%{IP:ip_foo}"},
            },
        }

        rule = NormalizerRule(LuceneFilter.create(grok_rule["filter"]), grok_rule["normalize"])
        assert len(rule.grok) == 1
        assert rule.grok.get("some_grok_field")._grok_list[0].pattern == "^%{IP:ip_foo}$"

    def test_grok_loads_one_pattern_from_list(self):
        grok_rule = {
            "filter": "message",
            "normalize": {
                "some_grok_field": {"grok": ["%{IP:ip_foo}"]},
            },
        }

        rule = NormalizerRule(LuceneFilter.create(grok_rule["filter"]), grok_rule["normalize"])
        assert len(rule.grok) == 1
        patterns = [grok.pattern for grok in rule.grok.get("some_grok_field")._grok_list]
        assert len(patterns) == 1
        assert patterns[0] == "^%{IP:ip_foo}$"

    def test_grok_loads_multiple_patterns_from_one_list(self):
        grok_patterns = ["%{IP:ip_foo}", "%{IP:ip_bar}", "%{IP:ip_baz}"]
        grok_rule = {
            "filter": "message",
            "normalize": {
                "some_grok_field": {"grok": grok_patterns},
            },
        }

        rule = NormalizerRule(LuceneFilter.create(grok_rule["filter"]), grok_rule["normalize"])
        assert len(rule.grok) == 1
        patterns = [grok.pattern for grok in rule.grok.get("some_grok_field")._grok_list]
        assert len(patterns) == 3
        assert patterns == ["^%{IP:ip_foo}$", "^%{IP:ip_bar}$", "^%{IP:ip_baz}$"]

    def test_grok_loads_multiple_patterns_from_multiple_lists(self):
        grok_rule = {
            "filter": "message",
            "normalize": {
                "some_grok_field_1": {"grok": ["%{IP:ip_foo}"]},
                "some_grok_field_2": {"grok": ["%{IP:ip_bar}"]},
                "some_grok_field_3": {"grok": ["%{IP:ip_baz}"]},
            },
        }

        rule = NormalizerRule(LuceneFilter.create(grok_rule["filter"]), grok_rule["normalize"])

        assert len(rule.grok) == 3
        patterns = [grok.pattern for grok in rule.grok.get("some_grok_field_1")._grok_list]
        assert len(patterns) == 1
        assert patterns[0] == "^%{IP:ip_foo}$"

        patterns = [grok.pattern for grok in rule.grok.get("some_grok_field_2")._grok_list]
        assert len(patterns) == 1
        assert patterns[0] == "^%{IP:ip_bar}$"

        patterns = [grok.pattern for grok in rule.grok.get("some_grok_field_3")._grok_list]
        assert len(patterns) == 1
        assert patterns[0] == "^%{IP:ip_baz}$"
