# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = [
    (
        "single field with ipv4 address",
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
            },
        },
        {"ip": "192.168.5.1"},
        {
            "ip": "192.168.5.1",
            "result": {
                "192.168.5.1": {
                    "compressed": "192.168.5.1",
                    "exploded": "192.168.5.1",
                    "is_global": False,
                    "is_link_local": False,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_unspecified": False,
                    "max_prefixlen": 32,
                    "packed": b"\xc0\xa8\x05\x01",
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
                }
            },
        },
    ),
    (
        "single field with ipv6 address",
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
            },
        },
        {"ip": "fe80::2c71:58ff:fe6a:5a08"},
        {
            "ip": "fe80::2c71:58ff:fe6a:5a08",
            "result": {
                "fe80::2c71:58ff:fe6a:5a08": {
                    "compressed": "fe80::2c71:58ff:fe6a:5a08",
                    "exploded": "fe80:0000:0000:0000:2c71:58ff:fe6a:5a08",
                    "ipv4_mapped": None,
                    "is_global": False,
                    "is_link_local": True,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_site_local": False,
                    "is_unspecified": False,
                    "max_prefixlen": 128,
                    "packed": b"\xfe\x80\x00\x00\x00\x00\x00\x00,qX\xff\xfejZ\x08",
                    "reverse_pointer": "8.0.a.5.a.6.e.f.f.f.8.5.1.7.c.2.0.0.0.0.0.0.0.0.0.0.0.0.0.8.e.f.ip6.arpa",
                    "scope_id": None,
                    "sixtofour": None,
                    "teredo": None,
                    "version": 6,
                }
            },
        },
    ),
    (
        "list field with ipv4 and ipv6 addresses",
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
            },
        },
        {"ip": ["192.168.5.1", "fe80::2c71:58ff:fe6a:5a08"]},
        {
            "ip": ["192.168.5.1", "fe80::2c71:58ff:fe6a:5a08"],
            "result": {
                "192.168.5.1": {
                    "compressed": "192.168.5.1",
                    "exploded": "192.168.5.1",
                    "is_global": False,
                    "is_link_local": False,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_unspecified": False,
                    "max_prefixlen": 32,
                    "packed": b"\xc0\xa8\x05\x01",
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
                },
                "fe80::2c71:58ff:fe6a:5a08": {
                    "compressed": "fe80::2c71:58ff:fe6a:5a08",
                    "exploded": "fe80:0000:0000:0000:2c71:58ff:fe6a:5a08",
                    "ipv4_mapped": None,
                    "is_global": False,
                    "is_link_local": True,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_site_local": False,
                    "is_unspecified": False,
                    "max_prefixlen": 128,
                    "packed": b"\xfe\x80\x00\x00\x00\x00\x00\x00,qX\xff\xfejZ\x08",
                    "reverse_pointer": "8.0.a.5.a.6.e.f.f.f.8.5.1.7.c.2.0.0.0.0.0.0.0.0.0.0.0.0.0.8.e.f.ip6.arpa",
                    "scope_id": None,
                    "sixtofour": None,
                    "teredo": None,
                    "version": 6,
                },
            },
        },
    ),
    (
        "list and single field with ipv4 and ipv6 addresses",
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip", "single"],
                "target_field": "result",
            },
        },
        {"ip": ["192.168.5.1", "fe80::2c71:58ff:fe6a:5a08"], "single": "127.0.0.1"},
        {
            "ip": ["192.168.5.1", "fe80::2c71:58ff:fe6a:5a08"],
            "single": "127.0.0.1",
            "result": {
                "192.168.5.1": {
                    "compressed": "192.168.5.1",
                    "exploded": "192.168.5.1",
                    "is_global": False,
                    "is_link_local": False,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_unspecified": False,
                    "max_prefixlen": 32,
                    "packed": b"\xc0\xa8\x05\x01",
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
                },
                "fe80::2c71:58ff:fe6a:5a08": {
                    "compressed": "fe80::2c71:58ff:fe6a:5a08",
                    "exploded": "fe80:0000:0000:0000:2c71:58ff:fe6a:5a08",
                    "ipv4_mapped": None,
                    "is_global": False,
                    "is_link_local": True,
                    "is_loopback": False,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_site_local": False,
                    "is_unspecified": False,
                    "max_prefixlen": 128,
                    "packed": b"\xfe\x80\x00\x00\x00\x00\x00\x00,qX\xff\xfejZ\x08",
                    "reverse_pointer": "8.0.a.5.a.6.e.f.f.f.8.5.1.7.c.2.0.0.0.0.0.0.0.0.0.0.0.0.0.8.e.f.ip6.arpa",
                    "scope_id": None,
                    "sixtofour": None,
                    "teredo": None,
                    "version": 6,
                },
                "127.0.0.1": {
                    "compressed": "127.0.0.1",
                    "exploded": "127.0.0.1",
                    "is_global": False,
                    "is_link_local": False,
                    "is_loopback": True,
                    "is_multicast": False,
                    "is_private": True,
                    "is_reserved": False,
                    "is_unspecified": False,
                    "max_prefixlen": 32,
                    "packed": b"\x7f\x00\x00\x01",
                    "reverse_pointer": "1.0.0.127.in-addr.arpa",
                    "version": 4,
                },
            },
        },
    ),
]  # testcase, rule, event, expected

failure_test_cases = []  # testcase, rule, event, expected


class TestIpInformer(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "ip_informer",
        "specific_rules": ["tests/testdata/unit/ip_informer/specific/"],
        "generic_rules": ["tests/testdata/unit/ip_informer/generic/"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
