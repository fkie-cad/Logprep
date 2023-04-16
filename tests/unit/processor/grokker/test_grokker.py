# pylint: disable=missing-docstring
import logging
import re

import pytest

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
    (
        "loads custom patterns",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {"winlog.event_data.normalize me!": "%{CUSTOM_PATTERN_TEST:normalized}"}
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "Test"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "Test"},
            },
            "normalized": "Test",
        },
    ),
    (
        "example log message",
        {
            "filter": "message",
            "grokker": {
                "mapping": {
                    "message": "%{TIMESTAMP_ISO8601:@timestamp} %{LOGLEVEL:logLevel} %{GREEDYDATA:logMessage}"
                }
            },
        },
        {"message": "2020-07-16T19:20:30.45+01:00 DEBUG This is a sample log"},
        {
            "message": "2020-07-16T19:20:30.45+01:00 DEBUG This is a sample log",
            "@timestamp": "2020-07-16T19:20:30.45+01:00",
            "logLevel": "DEBUG",
            "logMessage": "This is a sample log",
        },
    ),
    (
        "example for ecs conform output",
        {
            "filter": "message",
            "grokker": {"mapping": {"message": "%{COMBINEDAPACHELOG}"}},
        },
        {
            "message": '127.0.0.1 - - [11/Dec/2013:00:01:45 -0800] "GET /xampp/status.php HTTP/1.1" 200 3891 "http://cadenza/xampp/navi.php" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:25.0) Gecko/20100101 Firefox/25.0"'
        },
        {
            "message": '127.0.0.1 - - [11/Dec/2013:00:01:45 -0800] "GET /xampp/status.php HTTP/1.1" 200 3891 "http://cadenza/xampp/navi.php" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:25.0) Gecko/20100101 Firefox/25.0"',
            "source": {"address": "127.0.0.1"},
            "timestamp": "11/Dec/2013:00:01:45 -0800",
            "http": {
                "request": {"method": "GET", "referrer": "http://cadenza/xampp/navi.php"},
                "version": "1.1",
                "response": {"status_code": 200, "body": {"bytes": 3891}},
            },
            "url": {"original": "/xampp/status.php"},
            "user_agent": {
                "original": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:25.0) Gecko/20100101 Firefox/25.0"
            },
        },
    ),
]

failure_test_cases = [
    (
        "writes failure tag if no grok patterns matches",
        {
            "filter": "grok_me",
            "grokker": {
                "mapping": {
                    "grok_me": [
                        "%{IP:some_ip_1} %{NUMBER:port_1:int} foo",
                        "%{IP:some_ip_2} %{NUMBER:port_2:int} bar",
                    ]
                }
            },
        },
        {"grok_me": "123.123.123.123 1234"},
        {"grok_me": "123.123.123.123 1234", "tags": ["_grokker_failure"]},
        "no grok pattern matched",
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
            "tags": ["_grokker_failure"],
        },
        "no grok pattern matched",
    ),
]  # testcase, rule, event, expected


class TestGrokker(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "grokker",
        "specific_rules": ["tests/testdata/unit/grokker/specific_rules"],
        "generic_rules": ["tests/testdata/unit/grokker/generic_rules"],
        "custom_patterns_dir": "tests/testdata/unit/normalizer/additional_grok_patterns",
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(
        self, caplog, testcase, rule, event, expected, error_message
    ):
        self._load_specific_rule(rule)
        self.object.setup()
        with caplog.at_level(logging.WARNING):
            self.object.process(event)
            assert re.match(rf".*{error_message}", caplog.text)
        assert event == expected, testcase
