# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases: list = [
    pytest.param(
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
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
                }
            },
        },
        id="single field with ipv4 address",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
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
                    "reverse_pointer": "8.0.a.5.a.6.e.f.f.f.8.5.1.7.c.2.0.0.0.0.0.0.0.0.0.0.0.0.0.8.e.f.ip6.arpa",
                    "scope_id": None,
                    "sixtofour": None,
                    "teredo": None,
                    "version": 6,
                }
            },
        },
        id="single field with ipv6 address",
    ),
    pytest.param(
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
                    "reverse_pointer": "8.0.a.5.a.6.e.f.f.f.8.5.1.7.c.2.0.0.0.0.0.0.0.0.0.0.0.0.0.8.e.f.ip6.arpa",
                    "scope_id": None,
                    "sixtofour": None,
                    "teredo": None,
                    "version": 6,
                },
            },
        },
        id="list field with ipv4 and ipv6 addresses",
    ),
    pytest.param(
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
                    "reverse_pointer": "1.0.0.127.in-addr.arpa",
                    "version": 4,
                },
            },
        },
        id="list and single field with ipv4 and ipv6 addresses",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
                "properties": ["is_loopback"],
            },
        },
        {"ip": "192.168.5.1"},
        {
            "ip": "192.168.5.1",
            "result": {
                "192.168.5.1": {
                    "is_loopback": False,
                }
            },
        },
        id="single field with ipv4 address and filtered properties",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
                "properties": ["teredo"],
            },
        },
        {"ip": "192.168.5.1"},
        {
            "ip": "192.168.5.1",
            "result": {
                "192.168.5.1": {
                    "teredo": False,
                }
            },
        },
        id="get field value for non existent property",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip", "does_not_exist"],
                "target_field": "result",
                "properties": ["teredo"],
                "ignore_missing_fields": True,
            },
        },
        {"ip": "192.168.5.1"},
        {
            "ip": "192.168.5.1",
            "result": {
                "192.168.5.1": {
                    "teredo": False,
                }
            },
        },
        id="ignore missing fields",
    ),
)  # testcase, rule, event, expected

failure_test_cases = normalize_test_cases(
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
            },
        },
        {"ip": "not an ip"},
        {"ip": "not an ip", "tags": ["_ip_informer_failure"]},
        id="single field is not a ip address",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip", "does_not_exist"],
                "target_field": "result",
                "properties": ["teredo"],
            },
        },
        {"ip": "192.168.5.1"},
        {
            "ip": "192.168.5.1",
            "result": {
                "192.168.5.1": {
                    "teredo": False,
                }
            },
            "tags": ["_ip_informer_missing_field_warning"],
        },
        id="missing fields",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip", "notip"],
                "target_field": "result",
            },
        },
        {"notip": "not an ip", "ip": "192.168.5.1"},
        {
            "notip": "not an ip",
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
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
                }
            },
            "tags": ["_ip_informer_failure"],
        },
        id="single field is not an ip address and other field is an ip address",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip", "notip"],
                "target_field": "result",
            },
        },
        {"notip": "not an ip", "ip": ["192.168.5.1", "127.0.0.1"]},
        {
            "notip": "not an ip",
            "ip": ["192.168.5.1", "127.0.0.1"],
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
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
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
                    "reverse_pointer": "1.0.0.127.in-addr.arpa",
                    "version": 4,
                },
            },
            "tags": ["_ip_informer_failure"],
        },
        id="single field is not an ip address and other field is a list with valid ips",
    ),
    pytest.param(
        {
            "filter": "ip",
            "ip_informer": {
                "source_fields": ["ip"],
                "target_field": "result",
            },
        },
        {"ip": ["192.168.5.1", "not valid", "127.0.0.1"]},
        {
            "ip": ["192.168.5.1", "not valid", "127.0.0.1"],
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
                    "reverse_pointer": "1.5.168.192.in-addr.arpa",
                    "version": 4,
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
                    "reverse_pointer": "1.0.0.127.in-addr.arpa",
                    "version": 4,
                },
            },
            "tags": ["_ip_informer_failure"],
        },
        id="not valid ip in list",
    ),
)


class TestIpInformer(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ip_informer",
        "rules": ["tests/testdata/unit/ip_informer/rules/"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert event == expected
