# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "matches simple grok pattern",
        {"filter": "message", "grokker": {"mapping": {"message": "this is the %{USER:userfield}"}}},
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "userfield": "MyUser586"},
    ),
    (
        "matches simple grok pattern with dotted field target",
        {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is the %{USER:user.subfield}"}},
        },
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "user": {"subfield": "MyUser586"}},
    ),
    (
        "matches simple grok pattern with logstash field target",
        {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is the %{USER:[user][subfield]}"}},
        },
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "user": {"subfield": "MyUser586"}},
    ),
    (
        "matches custom patterns",
        {
            "filter": "message",
            "grokker": {
                "mapping": {"message": "this is the %{CUSTOM_PATTERN:user.subfield}"},
                "patterns": {"CUSTOM_PATTERN": r"[^\s]*"},
            },
        },
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "user": {"subfield": "MyUser586"}},
    ),
    (
        "normalize from grok",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {"winlog.event_data.normalize me!": "%{IP:some_ip} %{NUMBER:port:int}"},
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            },
            "some_ip": "123.123.123.123",
            "port": 1234,
        },
    ),
    (
        "normalize from grok match only exact",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {"winlog.event_data.normalize me!": "%{IP:some_ip} %{NUMBER:port:int}"},
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "foo 123.123.123.123 1234 bar"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "foo 123.123.123.123 1234 bar"},
            },
        },
    ),
    (
        "grok list match first matching after skippng non matching",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ]
                }
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 bar"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 bar"},
            },
            "some_ip_2": "123.123.123.123",
            "port_2": 1234,
        },
    ),
    (
        "grok list match first matching after skippng non matching and does not match twice",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                        "%{IP:some_ip_3} %{NUMBER:port_3:int} bar",
                    ]
                }
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 bar"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234 bar"},
            },
            "some_ip_2": "123.123.123.123",
            "port_2": 1234,
        },
    ),
    (
        "grok list match none",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ]
                }
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 1234"},
            },
        },
    ),
    (
        "normalization from nested grok",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": r"%{IP:[parent][some_ip]} \w+ %{NUMBER:[parent][port]:int} %[ts]+ %{NUMBER:test:int}"
                },
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 555 1234 %ttss 11"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "123.123.123.123 555 1234 %ttss 11"},
            },
            "test": 11,
            "parent": {"some_ip": "123.123.123.123", "port": 1234},
        },
    ),
]

failure_test_cases = []  # testcase, rule, event, expected


class TestGrokker(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "grokker",
        "specific_rules": ["tests/testdata/unit/grokker/specific_rules"],
        "generic_rules": ["tests/testdata/unit/grokker/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
