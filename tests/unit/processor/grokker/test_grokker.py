# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
import re
from copy import deepcopy
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import ProcessingCriticalError
from logprep.util.getter import GetterFactory
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
        "grok list match first matching after skipping non matching",
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
        "grok list match first matching after skipping non matching and does not match twice",
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
        "grok list match first matching after skipping non matching with same target fields",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": [
                        "%{IP:some_ip} %{NUMBER:port:int} foo",
                        "%{IP:some_ip} %{NUMBER:port:int} bar",
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
            "some_ip": "123.123.123.123",
            "port": 1234,
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
    (
        "matches simple oniguruma pattern",
        {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is the (?<userfield>[A-Za-z0-9]+)"}},
        },
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "userfield": "MyUser586"},
    ),
    (
        "oniguruma with nested parentheses (3 levels supported)",
        {
            "filter": "message",
            "grokker": {
                "mapping": {
                    "message": "^(?<timestamp>%{DAY}%{SPACE}%{MONTH}%{SPACE}%{MONTHDAY}%{SPACE}%{TIME}%{SPACE}%{YEAR})%{SPACE}%{GREEDYDATA:[remains]}$",
                    "remains": "(?<action>(SEND%{SPACE}INFO)%{SPACE}(?<info>BAL)%{GREEDYDATA:rest}",
                }
            },
        },
        {"message": "Wed Dec 7 13:14:13 2005 SEND INFO BAL/4"},
        {
            "message": "Wed Dec 7 13:14:13 2005 SEND INFO BAL/4",
            "timestamp": "Wed Dec 7 13:14:13 2005",
            "action": "SEND INFO",
            "info": "BAL",
            "rest": "/4",
            "remains": "SEND INFO BAL/4",
        },
    ),
    (
        "two oniguruma with same target names, applies only the last target",
        {
            "filter": "message",
            "grokker": {
                "mapping": {
                    "message": "^(?<action>%{NUMBER})%{SPACE}(?<action>%{NUMBER})%{SPACE}(?<action>%{NUMBER})%{SPACE}(?<action>%{NUMBER})$",
                }
            },
        },
        {"message": "13 37 21 42"},
        {
            "message": "13 37 21 42",
            "action": "42",
        },
    ),
    (
        "ignore_missing_fields",
        {
            "filter": "winlog.event_id: 123456789",
            "grokker": {
                "mapping": {
                    "winlog.event_data.normalize me!": "%{IP:some_ip} %{NUMBER:port:int}",
                    "this_field_does_not_exist": "%{IP:some_ip} %{NUMBER:port:int}",
                },
                "ignore_missing_fields": True,
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
        "Subfield with common prefix",
        {
            "filter": "message",
            "grokker": {
                "mapping": {
                    "message": "Facility %{USER:facility.location} %{USER:facility.location_level}"
                }
            },
        },
        {"message": "Facility spain primary"},
        {
            "message": "Facility spain primary",
            "facility": {"location": "spain", "location_level": "primary"},
        },
    ),
]

failure_test_cases = [
    (
        "only field does not exist",
        {"filter": "message", "grokker": {"mapping": {"unknown": "this is the %{USER:userfield}"}}},
        {"message": "this is the MyUser586"},
        {"message": "this is the MyUser586", "tags": ["_grokker_missing_field_warning"]},
        r"missing source_fields: \['unknown']",
    ),
    (
        "only one field does not exist",
        {
            "filter": "message",
            "grokker": {
                "mapping": {
                    "message": "this is the %{USER:userfield}",
                    "unknown": "this is the %{USER:userfield}",
                }
            },
        },
        {"message": "this is the MyUser586"},
        {
            "message": "this is the MyUser586",
            "userfield": "MyUser586",
            "tags": ["_grokker_missing_field_warning"],
        },
        r"missing source_fields: \['unknown']",
    ),
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
    (
        "grok pattern timeout",
        {
            "filter": "url",
            "grokker": {
                "mapping": {
                    "url": "^(%{URIPROTO:[network][protocol]}://)?%{IPORHOST:[url][domain]}(?::%{POSINT:[url][port]})?(?:%{URIPATHPARAM:[url][path]})?$"
                }
            },
        },
        {"url": "is-ascdwa-fv458.sdcfvfdaq.ascg:316"},
        {"url": "is-ascdwa-fv458.sdcfvfdaq.ascg:316"},
        ProcessingCriticalError,
    ),
]  # testcase, rule, event, expected


class TestGrokker(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "grokker",
        "rules": ["tests/testdata/unit/grokker/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error):
        self._load_rule(rule)
        self.object.setup()
        if isinstance(error, str):
            result = self.object.process(event)
            assert len(result.warnings) == 1
            assert re.match(rf".*{error}", str(result.warnings[0]))
            assert event == expected, testcase
        else:
            result = self.object.process(event)
            assert isinstance(result.errors[0], ProcessingCriticalError)

    def test_load_custom_patterns_from_http_as_zip_file(self):
        rule = {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is %{ID:userfield}"}},
        }

        event = {"message": "this is user-456"}
        expected = {"message": "this is user-456", "userfield": "user-456"}
        archive_data = GetterFactory.from_string(
            "tests/testdata/unit/grokker/patterns.zip"
        ).get_raw()
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_getter:
            mock_getter.return_value = archive_data
            config = deepcopy(self.CONFIG)
            config["custom_patterns_dir"] = (
                "http://localhost:8000/tests/testdata/unit/grokker/patterns.zip"
            )
            self.object = Factory.create({"grokker": config})
            self._load_rule(rule)
            self.object.setup()
        self.object.process(event)
        assert event == expected

    def test_loads_patterns_without_custom_patterns_dir(self):
        config = deepcopy(self.CONFIG)
        config |= {
            "custom_patterns_dir": "",
        }
        grokker = Factory.create({"grokker": config})
        assert len(grokker.rules) > 0

    def test_loads_custom_patterns(self):
        rule = {
            "filter": "winlog.event_id: 123456789",
            "grokker": {"mapping": {"winlog.event_data.normalize me!": "%{ID:normalized}"}},
        }
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "id-1"},
            }
        }
        expected = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "id-1"},
            },
            "normalized": "id-1",
        }
        config = deepcopy(self.CONFIG)
        config["custom_patterns_dir"] = "tests/testdata/unit/grokker/patterns/"
        self.object = Factory.create({"grokker": config})
        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected
