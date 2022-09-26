# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-lines
# pylint: disable=line-too-long
import calendar
import copy
import json
import os
import tempfile
from copy import deepcopy

import arrow
import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.normalizer.exceptions import NormalizerError
from logprep.processor.normalizer.rule import (
    InvalidGrokDefinition,
    InvalidNormalizationDefinition,
    NormalizerRule,
)
from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase


class TestNormalizer(BaseProcessorTestCase):

    CONFIG = {
        "type": "normalizer",
        "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
        "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
        "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
    }

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    def test_process_normalized_field_already_exists_with_same_content(self):
        document = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1234,
                "event_data": {"test_normalize": "Existing and normalized have the same value"},
                "test_normalized": {"something": "Existing and normalized have the same value"},
            }
        }
        try:
            self.object.process(document)
        except ProcessingWarning:
            pytest.fail(
                "Normalization over an existing field with the same value as the normalized"
                " field should not raise a ProcessingWarning!"
            )

        assert (
            document["test_normalized"]["something"]
            == "Existing and normalized have the same value"
        )

    def test_process_normalized_field_already_exists_with_different_content(self):
        document = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1234,
                "event_data": {"test_normalize": "I am new and want to be normalized!"},
            },
            "test_normalized": {"something": "I already exist but I am different!"},
        }
        with pytest.raises(
            ProcessingWarning,
            match=r"The following fields already existed and were not "
            r"overwritten by the Normalizer: test_normalized.something\)",
        ):
            self.object.process(document)

        assert document["test_normalized"]["something"] == "I already exist but I am different!"

    def test_apply_windows_rules_catch_all(self):
        document = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1234,
                "event_data": {"test_normalize": "foo"},
            }
        }
        self.object.process(document)
        assert document["test_normalized"]["something"] == "foo"

    def test_apply_windows_rules_for_specific_event_id(self):
        document = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1111,
                "event_data": {"test1": "foo"},
            }
        }
        self.object.process(document)
        assert document["test_normalized"]["test1"] == "foo"

        document = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1112,
                "event_data": {"test1": "foo"},
            }
        }
        self.object.process(document)
        assert "test1" not in document.get("test_normalized", {})

    def test_add_field_without_conflicts(self):
        event = {"host": {"ip": "127.0.0.1"}, "client": {"port": 22222}}
        self.object._add_field(event, "foo.bar.baz", 1234)
        self.object._add_field(event, "host.user.name", "admin")
        self.object._add_field(event, "client.address", "localhost")
        assert event == {
            "foo": {"bar": {"baz": 1234}},
            "host": {"ip": "127.0.0.1", "user": {"name": "admin"}},
            "client": {"address": "localhost", "port": 22222},
        }
        assert not self.object._conflicting_fields

    def test_add_field_with_conflicts(self):
        event = {"host": "localhost"}
        self.object._add_field(event, "host.user.name", "admin")
        assert self.object._conflicting_fields == ["host.user.name"]

    def test_normalization_from_specific_rules(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1111,
                "event_data": {
                    "param1": "Do not normalize me!",
                    "test1": "Normalize me!",
                },
            }
        }

        self.object.process(event)

        assert event["winlog"]["event_data"]["param1"] == "Do not normalize me!"
        assert event["test_normalized"]["test1"] == "Normalize me!"

    def test_normalization_from_specific_rule_with_multiple_matching_fields(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 2222,
                "event_data": {
                    "param1": "Do not normalize me!",
                    "Test1": "Normalize me.",
                    "Test2": "Normalize me!",
                },
            }
        }

        self.object.process(event)

        assert event["winlog"]["event_data"]["param1"] == "Do not normalize me!"
        assert event["test_normalized"]["test"]["field1"] == "Normalize me."
        assert event["test_normalized"]["test"]["field2"] == "Normalize me!"

    def test_normalization_from_generic_rules(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1234,
                "event_data": {
                    "param1": "Do not normalize me!",
                    "test1": "Normalize me!",
                },
            }
        }

        self.object.process(event)

        assert event["winlog"]["event_data"]["param1"] == "Do not normalize me!"
        assert event["test_normalized"]["something"] == "Normalize me!"

    def test_normalize_with_invalid_list_fails(self):
        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {"winlog.event_data.invalid_normalization": ["I am normalized!", ""]},
        }

        with pytest.raises(InvalidNormalizationDefinition):
            self._load_specific_rule(rule)

    def test_normalize_full_field_with_regex_succeeds(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "Source value"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": [
                    "I am normalized!",
                    "RE_FULL_CAP",
                    r"\g<ALL>",
                ]
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["I am normalized!"] == "Source value"

    def test_normalize_full_field_with_regex_extraction_succeeds(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "xyz Only this! xyz"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": [
                    "I am normalized!",
                    "RE_ONLY_THIS_CAP",
                    r"\g<ONLY_THIS>",
                ]
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["I am normalized!"] == "Only this!"

    def test_normalize_full_field_with_non_matching_regex(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "Keep it as is!"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": [
                    "I am normalized!",
                    r"no match",
                    r"does not matter",
                ]
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["I am normalized!"] == "Keep it as is!"

    def test_normalize_full_field_with_regex_rearrange_succeeds(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "Second comes not before First"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": [
                    "I am normalized!",
                    "RE_SWITCH_CAP",
                    r"\g<FIRST> comes before \g<SECOND>",
                ]
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["I am normalized!"] == "First comes before Second"

    def test_normalization_from_grok(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:some_ip} %{NUMBER:port:int}"}
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") == "123.123.123.123"
        assert event.get("port") == 1234

    def test_normalization_from_grok_match_only_exact(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "foo 123.123.123.123 1234 bar"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:some_ip} %{NUMBER:port:int}"}
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") is None
        assert event.get("port") is None

    def test_normalization_from_grok_does_not_match(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:some_ip} %{NUMBER:port:int}"}
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") is None
        assert event.get("port") is None

    def test_normalization_from_grok_list_match_first_matching(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int}",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int}",
                    ]
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") == "123.123.123.123"
        assert event.get("port_1") == 1234
        assert event.get("some_ip_2") is None
        assert event.get("port_2") is None

    def test_normalization_from_grok_list_match_first_matching_after_skipping_non_matching(
        self,
    ):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 bar"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ]
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") is None
        assert event.get("port_1") is None
        assert event.get("some_ip_2") == "123.123.123.123"
        assert event.get("port_2") == 1234

    def test_normalization_from_grok_list_match_none(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ]
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") is None
        assert event.get("port_1") is None
        assert event.get("some_ip_2") is None
        assert event.get("port_2") is None

    def test_normalization_from_nested_grok(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 555 1234 %ttss 11"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": r"%{IP:[parent][some_ip]} \w+ %{NUMBER:[parent][port]:int} %[ts]+ %{NUMBER:test:int}"
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("test") == 11
        assert event.get("parent")
        assert event["parent"].get("some_ip") == "123.123.123.123"
        assert event["parent"].get("port") == 1234

    def test_normalization_from_grok_with_custom_patterns(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123456 Test other file!"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": "%{CUSTOM_PATTERN_123456:custom_123456} %{CUSTOM_PATTERN_Test:custom_Test} %{CUSTOM_PATTERN_OTHER_FILE:custom_other_file}"
                }
            },
        }

        with pytest.raises(InvalidGrokDefinition):
            self._load_specific_rule(rule)

        NormalizerRule.additional_grok_patterns = (
            "tests/testdata/unit/normalizer/additional_grok_patterns"
        )
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("custom_123456") == "123456"
        assert event.get("custom_Test") == "Test"
        assert event.get("custom_other_file") == "other file!"

    def test_normalization_from_grok_and_norm_result(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:some_ip} %{NUMBER:port:int}"},
                "some_ip": "some.ip",
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") == "123.123.123.123"
        assert event.get("port") == 1234
        assert event.get("some")
        assert event["some"].get("ip") == "123.123.123.123"

    def test_normalization_from_grok_writes_grok_failure_if_no_grok_pattern_matches_and_if_configured(
        self,
    ):
        event = {"grok_me": "123.123.123.123 1234"}

        rule = {
            "filter": "grok_me",
            "normalize": {
                "grok_me": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ],
                    "failure_target_field": "grok_failure",
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") is None
        assert event.get("port_1") is None
        assert event.get("some_ip_2") is None
        assert event.get("port_2") is None
        assert event.get("grok_failure") == {"grok_me": "123.123.123.123 1234"}

    def test_normalization_from_grok_writes_grok_failure_for_nested_fields(
        self,
    ):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ],
                    "failure_target_field": "grok_failure",
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") is None
        assert event.get("port_1") is None
        assert event.get("some_ip_2") is None
        assert event.get("port_2") is None
        assert event.get("grok_failure") == {
            "winlog>event_data>normalize me!": "123.123.123.123 1234"
        }

    def test_normalization_from_grok_writes_grok_failure_to_dotted_subfield(
        self,
    ):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ],
                    "failure_target_field": "winlog.event_data.grok_failure",
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip_1") is None
        assert event.get("port_1") is None
        assert event.get("some_ip_2") is None
        assert event.get("port_2") is None
        assert event.get("winlog", {}).get("event_data", {}).get("grok_failure") == {
            "winlog>event_data>normalize me!": "123.123.123.123 1234"
        }

    def test_normalization_from_grok_onto_existing(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:winlog} %{NUMBER:port:int}"}
            },
        }

        self._load_specific_rule(rule)

        with pytest.raises(
            ProcessingWarning,
            match=r"The following fields already existed and were not "
            r"overwritten by the Normalizer: winlog\)",
        ):
            self.object.process(event)

    def test_incorrect_grok_identifier_definition(self):
        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"groks": "%{IP:some_ip} %{NUMBER:port:int}"}
            },
        }

        with pytest.raises(InvalidNormalizationDefinition):
            self._load_specific_rule(rule)

    def test_incorrect_grok_definition(self):
        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {"grok": "%{IP:some_ip} %{NUMBA:port:int}"}
            },
        }

        with pytest.raises(InvalidGrokDefinition):
            self._load_specific_rule(rule)

    def test_normalization_from_timestamp_berlin_to_utc(self):
        expected = {
            "@timestamp": "1999-12-12T11:12:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "Europe/Berlin",
                        "destination_timezone": "UTC",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_grok_with_timestamp_normalization(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 1999 12 12 - 12:12:22"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": "%{IP:some_ip} %{NUMBER:port:int} %{CUSTOM_TIMESTAMP:some_timestamp_utc}"
                },
                "some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "UTC",
                        "destination_timezone": "UTC",
                    }
                },
            },
        }

        NormalizerRule.additional_grok_patterns = (
            "tests/testdata/unit/normalizer/additional_grok_patterns"
        )
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") == "123.123.123.123"
        assert event.get("port") == 1234
        assert event.get("@timestamp") == "1999-12-12T12:12:22Z"

    def test_normalization_from_grok_with_timestamp_normalization_and_timestamp_does_not_exist(
        self,
    ):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": [
                        "%{IP:some_ip} %{NUMBER:port:int} %{CUSTOM_TIMESTAMP:some_timestamp_utc}",
                        "%{IP:some_ip} %{NUMBER:port:int}",
                    ]
                },
                "some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "UTC",
                        "destination_timezone": "UTC",
                    }
                },
            },
        }

        NormalizerRule.additional_grok_patterns = (
            "tests/testdata/unit/normalizer/additional_grok_patterns"
        )
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event.get("some_ip") == "123.123.123.123"
        assert event.get("port") == 1234
        assert event.get("@timestamp") is None

    def test_normalization_from_timestamp_same_timezones(self):
        expected = {
            "@timestamp": "1999-12-12T12:12:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "UTC",
                        "destination_timezone": "UTC",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_timestamp_utc_to_berlin(self):
        expected = {
            "@timestamp": "1999-12-12T13:12:22+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "UTC",
                        "destination_timezone": "Europe/Berlin",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_iso8601_timestamp(self):
        expected = {
            "@timestamp": "2020-01-03T14:04:05.879000Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "2020-01-03T14:04:05.879Z"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "2020-01-03T14:04:05.879Z"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "ISO8601"],
                        "source_timezone": "Europe/Berlin",
                        "destination_timezone": "UTC",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_unix_with_millis_timestamp(self):
        expected = {
            "@timestamp": "2022-01-14T12:40:49.843000+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449843"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449843"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["UNIX"],
                        "source_timezone": "UTC",
                        "destination_timezone": "Europe/Berlin",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_unix_with_seconds_timestamp(self):
        expected = {
            "@timestamp": "2022-01-14T12:40:49+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            },
        }

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["UNIX"],
                        "source_timezone": "UTC",
                        "destination_timezone": "Europe/Berlin",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_non_matching_patterns(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22 UTC"},
            }
        }

        expected = copy.deepcopy(event)

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["a%Y", "a%Y %m", "ISO8601"],
                        "source_timezone": "UTC",
                        "destination_timezone": "Europe/Berlin",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        with pytest.raises(NormalizerError):
            self.object.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_collision(self):
        expected = {
            "@timestamp": "1999-12-12T11:12:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        event = {
            "@timestamp": "2200-02-01T16:19:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "Europe/Berlin",
                        "destination_timezone": "UTC",
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_collision_without_allow_override_fails(
        self,
    ):
        event = {
            "@timestamp": "2200-02-01T16:19:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        }

        expected = copy.deepcopy(event)

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.some_timestamp_utc": {
                    "timestamp": {
                        "destination": "@timestamp",
                        "source_formats": ["%Y", "%Y %m %d - %H:%M:%S"],
                        "source_timezone": "Europe/Berlin",
                        "destination_timezone": "UTC",
                        "allow_override": False,
                    }
                }
            },
        }

        self._load_specific_rule(rule)
        with pytest.raises(
            ProcessingWarning,
            match=r"The following fields already existed and were not "
            r"overwritten by the Normalizer: @timestamp\)",
        ):
            self.object.process(event)

        assert event == expected

    def test_normalization_with_replace_html_entity(self):
        event = {
            "tags": ["testtag"],
            "message": "replace=MAX&#43;&#8364;MORITZ&amp;dont_replace=FOO&#43;BAR&amp;id=5",
        }

        expected = {
            "tags": ["testtag"],
            "message": "replace=MAX&#43;&#8364;MORITZ&amp;dont_replace=FOO&#43;BAR&amp;id=5",
            "test": {
                "id": "5",
                "dont_replace": "FOO&#43;BAR",
                "replace": "MAX&#43;&#8364;MORITZ",
                "replace_decodiert": "MAX+€MORITZ",
            },
        }

        rule = {
            "filter": "tags: testtag",
            "normalize": {
                "message": {
                    "grok": "replace=%{DATA:[test][replace]}"
                    "&amp;dont_replace=%{DATA:[test][dont_replace]}&amp;id=%{INT:[test][id]}"
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        assert event == expected

    def test_normalization_with_grok_pattern_count(self):
        temp_path = tempfile.mkdtemp()
        config = deepcopy(self.CONFIG)

        config.update(
            {"count_grok_pattern_matches": {"count_directory_path": temp_path, "write_period": 0}}
        )
        processor_config = {"Test Normalizer Name": config}
        self.object = Factory.create(processor_config, self.logger)

        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        }

        rule = {
            "filter": "winlog.event_id: 123456789",
            "normalize": {
                "winlog.event_data.normalize me!": {
                    "grok": ["%{IP:some_ip} %{NUMBER:port:int}", "NO MATCH"]
                }
            },
        }

        self._load_specific_rule(rule)
        self.object.process(event)

        match_cnt_path = self.object._grok_matches_path
        match_cnt_files = os.listdir(match_cnt_path)

        assert len(match_cnt_files) == 1

        now = arrow.now()
        date = now.date()
        match_file_name = match_cnt_files[0]

        assert match_file_name.endswith(".json")

        file_date, file_weekday = match_cnt_files[0][:-5].split("_")

        assert date.isoformat() == file_date
        assert calendar.day_name[date.weekday()].lower() == file_weekday

        with open(
            os.path.join(match_cnt_path, match_file_name), "r", encoding="utf8"
        ) as match_file:
            match_json = json.load(match_file)

            assert "^%{IP:some_ip} %{NUMBER:port:int}$" in match_json
            assert "^NO MATCH$" in match_json
            assert match_json["^%{IP:some_ip} %{NUMBER:port:int}$"] == 1
            assert match_json["^NO MATCH$"] == 0

        self.object.process(event)

        with open(
            os.path.join(match_cnt_path, match_file_name), "r", encoding="utf8"
        ) as match_file:
            match_json = json.load(match_file)

            assert match_json["^%{IP:some_ip} %{NUMBER:port:int}$"] == 2
            assert match_json["^NO MATCH$"] == 0

        assert event.get("some_ip") == "123.123.123.123"
        assert event.get("port") == 1234
