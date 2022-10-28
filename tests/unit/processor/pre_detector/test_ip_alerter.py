# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
from ipaddress import IPv4Network

import pytest

pytest.importorskip("logprep.processor.pre_detector")

from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.processor.pre_detector.ip_alerter import IPAlerter

IP_ALERTS_PATH = "tests/testdata/unit/pre_detector/alert_ips.yml"
IP_ALERTS_PATHS_LIST = [
    "tests/testdata/unit/pre_detector/alert_ips_1.yml",
    "tests/testdata/unit/pre_detector/alert_ips_2.yml",
]


@pytest.fixture(name="ip_alerter")
def fixture_ip_alerter():
    return IPAlerter(IP_ALERTS_PATH)


@pytest.fixture(name="rule_without_fields")
def fixture_rule_without_fields():
    return PreDetectorRule._create_from_dict(
        {
            "filter": "message",
            "pre_detector": {
                "id": "does not matter",
                "title": "does not matter",
                "severity": "doesnotcare",
                "mitre": [],
                "case_condition": "does not care",
            },
        }
    )


@pytest.fixture(name="rule_with_fields")
def fixture_rule_with_fields():
    return PreDetectorRule._create_from_dict(
        {
            "filter": "message",
            "pre_detector": {
                "id": "does not matter",
                "title": "does not matter",
                "severity": "doesnotcare",
                "mitre": [],
                "case_condition": "does not care",
            },
            "ip_fields": ["ip_field"],
        }
    )


class TestIPAlerter:
    def test_ip_alerter_initialization(self, ip_alerter):
        expected_alert_ips = {
            "12.12.12.12": "2027-08-31T16:47+00:00",
            "13.12.12.13": None,
            "27.0.0.1": "2077-08-31T16:47+00:00",
            "127.0.0.0/8": "2077-08-31T16:47+00:00",
            "127.0.0.1": "2077-08-31T16:47+00:00",
        }
        expected_single_alert_ips = {"27.0.0.1", "13.12.12.13", "127.0.0.1", "12.12.12.12"}
        expected_alert_networks = {IPv4Network("127.0.0.0/8")}

        assert ip_alerter._alert_ips_map == expected_alert_ips
        assert ip_alerter._single_alert_ips == expected_single_alert_ips
        assert ip_alerter._alert_network == expected_alert_networks

    def test_ip_alerter_initialization_from_multiple_files(self):
        expected_alert_ips = {
            "12.12.12.12": "2027-08-31T16:47+00:00",
            "13.12.12.13": None,
            "27.0.0.1": "2077-08-31T16:47+00:00",
            "127.0.0.0/8": "2077-08-31T16:47+00:00",
            "127.0.0.1": "2077-08-31T16:47+00:00",
        }
        expected_single_alert_ips = {"27.0.0.1", "13.12.12.13", "127.0.0.1", "12.12.12.12"}
        expected_alert_networks = {IPv4Network("127.0.0.0/8")}

        ip_alerter = IPAlerter(IP_ALERTS_PATHS_LIST)

        assert ip_alerter._alert_ips_map == expected_alert_ips
        assert ip_alerter._single_alert_ips == expected_single_alert_ips
        assert ip_alerter._alert_network == expected_alert_networks

    def test_ip_alerter_has_no_fields_fails(self, ip_alerter, rule_without_fields):
        assert not ip_alerter.has_ip_fields(rule_without_fields)

    def test_ip_is_in_alerts_single_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "12.12.12.12"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_single_but_also_network_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.0.1"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_single_without_time_limit_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "13.12.12.13"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_network_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.123.1"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_single_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "227.0.0.1"}
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_network_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "128.0.0.1"}
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_single_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "12.12.12.12"}
        ip_alerter._alert_ips_map["12.12.12.12"] = "1900-08-31T16:47+00:00"
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_single_and_network_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.0.1"}
        ip_alerter._alert_ips_map["127.0.0.1"] = "1900-08-31T16:47+00:00"
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_network_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.1.1"}
        ip_alerter._alert_ips_map["127.0.0.0/8"] = "1900-08-31T16:47+00:00"
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_field_does_not_exist(self, ip_alerter, rule_with_fields):
        event = {}
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)
