# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=unused-argument
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-arguments


from uuid import uuid4

import pytest

from logprep.factory_error import InvalidConfigurationError

pytest.importorskip("logprep.processor.pre_detector")

from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.processor.pre_detector.ip_alerter import IPAlerter, IPVersion

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
    return PreDetectorRule.create_from_dict(
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
    return PreDetectorRule.create_from_dict(
        {
            "filter": "message",
            "pre_detector": {
                "id": "does not matter",
                "title": "does not matter",
                "severity": "doesnotcare",
                "mitre": [],
                "case_condition": "does not care",
            },
            "ip_fields": ["ip_field", "ip_field_2"],
        }
    )


class TestIPAlerter:
    def test_ip_alerter_initialization(self, ip_alerter):
        assert ip_alerter._permanent_ips[IPVersion.V4] == {"13.12.12.13"}
        assert ip_alerter._permanent_ips[IPVersion.V6] == {281470900636685}  # ::ffff:0d0c:0c0d
        assert ip_alerter._expiring_ips[IPVersion.V4] == {
            "12.12.12.12": 1819730820.0,  # 2027-08-31T16:47+00:00
            "27.0.0.1": 3397654020.0,  # 2077-08-31T16:47+00:00
            "127.0.0.1": 3397654020.0,  # 2077-08-31T16:47+00:00
        }
        assert ip_alerter._expiring_ips[IPVersion.V6] == {1: 3397654020.0}  # ::1

        assert ip_alerter._permanent_cidrs[IPVersion.V4] == {
            4294967040: {235670528}  # 14.12.12.0/24
        }
        assert ip_alerter._permanent_cidrs[IPVersion.V6] == {}

        net_mask = ip_alerter._get_net_mask(IPVersion.V4, 8)
        expiring_cidrs_for_mask = {net_mask: {2130706432: 3397654020.0}}  # 127.0.0.0/8
        assert ip_alerter._expiring_cidrs[IPVersion.V4] == expiring_cidrs_for_mask

        net_mask = ip_alerter._get_net_mask(IPVersion.V6, 126)
        expiring_cidrs_for_mask = {net_mask: {0: 3397654020.0}}  # ::/126
        assert ip_alerter._expiring_cidrs[IPVersion.V6] == expiring_cidrs_for_mask

    def test_ip_alerter_initialization_from_multiple_files(self):
        ip_alerter = IPAlerter(IP_ALERTS_PATHS_LIST)
        assert ip_alerter._permanent_ips[IPVersion.V4] == {"13.12.12.13"}
        assert ip_alerter._permanent_ips[IPVersion.V6] == set()
        assert ip_alerter._expiring_ips[IPVersion.V4] == {
            "12.12.12.12": 1819730820.0,  # 2027-08-31T16:47+00:00
            "27.0.0.1": 3397654020.0,  # 2077-08-31T16:47+00:00
            "127.0.0.1": 3397654020.0,  # 2077-08-31T16:47+00:00
        }
        assert ip_alerter._expiring_ips[IPVersion.V6] == {}

        assert ip_alerter._permanent_cidrs[IPVersion.V4] == {}
        assert ip_alerter._permanent_cidrs[IPVersion.V6] == {}

        net_mask = ip_alerter._get_net_mask(IPVersion.V4, 8)
        expiring_cidrs_for_mask = {net_mask: {2130706432: 3397654020.0}}  # 127.0.0.0/8
        assert ip_alerter._expiring_cidrs[IPVersion.V4] == expiring_cidrs_for_mask
        assert ip_alerter._expiring_cidrs[IPVersion.V6] == {}

    def test_ip_alerter_initialization_with_empty_list(self):
        ip_alerter = IPAlerter([])
        assert all(len(v) == 0 for v in ip_alerter._permanent_ips.values())
        assert all(len(v) == 0 for v in ip_alerter._expiring_ips.values())
        assert all(len(v) == 0 for v in ip_alerter._permanent_cidrs.values())
        assert all(len(v) == 0 for v in ip_alerter._expiring_cidrs.values())
        assert ip_alerter._permanent_ips[IPVersion.V4] == set()
        assert ip_alerter._expiring_ips[IPVersion.V4] == {}
        assert ip_alerter._permanent_cidrs[IPVersion.V4] == {}
        assert ip_alerter._expiring_cidrs[IPVersion.V4] == {}

    def test_ip_alerter_initialization_with_none_list(self):
        ip_alerter = IPAlerter(None)
        assert all(len(v) == 0 for v in ip_alerter._permanent_ips.values())
        assert all(len(v) == 0 for v in ip_alerter._expiring_ips.values())
        assert all(len(v) == 0 for v in ip_alerter._permanent_cidrs.values())
        assert all(len(v) == 0 for v in ip_alerter._expiring_cidrs.values())
        assert ip_alerter._permanent_ips[IPVersion.V4] == set()
        assert ip_alerter._expiring_ips[IPVersion.V4] == {}
        assert ip_alerter._permanent_cidrs[IPVersion.V4] == {}
        assert ip_alerter._expiring_cidrs[IPVersion.V4] == {}

    def test_ip_alerter_initialization_without_existing_file(self):
        file_path = str(uuid4())
        with pytest.raises(
            InvalidConfigurationError, match=rf"Mapping file does not exist: {file_path}"
        ):
            IPAlerter(file_path)

    def test_ip_alerter_initialization_with_list_content(self, tmp_path):
        temp_file = tmp_path / f"{uuid4()}"
        with temp_file.open("w", encoding="utf-8") as f:
            f.write('["test"]')
        with pytest.raises(ValueError, match=r"expected a mapping and not a list"):
            IPAlerter(temp_file.as_posix())

    def test_add_invalid_cidr(self, ip_alerter):
        cidr = "127.0.0.0/33"
        with pytest.raises(
            InvalidConfigurationError,
            match=rf"IPv4 CIDR mask invalid for {cidr}",
        ):
            ip_alerter._add_cidr(cidr, IPVersion.V4, None)

        cidr = "ee00:a3de:e577:f4f2:3ff9:a0a6:c60c:d63d/129"
        with pytest.raises(
            InvalidConfigurationError,
            match=rf"IPv6 CIDR mask invalid for {cidr}",
        ):
            ip_alerter._add_cidr(cidr, IPVersion.V6, None)

    def test_add_cidr_without_expiration_time(self, ip_alerter):
        cidr = "127.0.0.0/32"
        ip_alerter._permanent_cidrs[IPVersion.V4].clear()
        ip_alerter._add_cidr(cidr, IPVersion.V4, None)
        assert ip_alerter._permanent_cidrs[IPVersion.V4] == {4294967295: {2130706432}}

    def test_ipv6_notation_is_equivalent(self, ip_alerter):
        compressed = ip_alerter._convert_ipv6_to_int("::ffff:0d0c:0c0d")
        shorthand = ip_alerter._convert_ipv6_to_int("0:0:0:0:0:ffff:0d0c:0c0d")
        exploded = ip_alerter._convert_ipv6_to_int("0000:0000:0000:0000:0000:ffff:0d0c:0c0d")
        dot_notation = ip_alerter._convert_ipv6_to_int("::ffff:13.12.12.13")
        assert compressed == shorthand
        assert shorthand == exploded
        assert exploded == dot_notation

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

    def test_ip_is_in_alerts_network_without_time_limit_succeeds(
        self, ip_alerter, rule_with_fields
    ):
        event = {"ip_field": "14.12.12.123"}
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

    def test_compressed_ipv6_ip_is_in_alerts_single_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "::ffff:0d0c:0c0d"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_exploded_ipv6_ip_is_in_alerts_single_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "0000:0000:0000:0000:0000:ffff:0d0c:0c0d"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_dotted_ipv6_ip_is_in_alerts_single_succeeds(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "::ffff:13.12.12.13"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_single_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "12.12.12.12"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)
        ip_alerter._expiring_ips[IPVersion.V4]["12.12.12.12"] = 0.0
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_single_exceeded_twice_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "12.12.12.12"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)
        ip_alerter._expiring_ips[IPVersion.V4]["12.12.12.12"] = 0.0
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_single_and_network_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.0.1"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)
        ip_alerter._expiring_ips[IPVersion.V4]["127.0.0.1"] = 0.0
        net_mask = ip_alerter._get_net_mask(IPVersion.V4, 8)
        ip_alerter._expiring_cidrs[IPVersion.V4][net_mask][2130706432] = 0.0  # 127.0.0.0/8
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_time_network_exceeded_fails(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.1.1"}
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)
        net_mask = ip_alerter._get_net_mask(IPVersion.V4, 8)
        ip_alerter._expiring_cidrs[IPVersion.V4][net_mask][2130706432] = 0.0  # 127.0.0.0/8
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_field_does_not_exist(self, ip_alerter, rule_with_fields):
        event = {}
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_is_in_alerts_single_empty_sets(self, ip_alerter, rule_with_fields):
        event = {"ip_field": "127.0.0.1"}
        ip_alerter = IPAlerter([])
        assert not ip_alerter.is_in_alerts_list(rule_with_fields, event)

    def test_ip_to_int_fails_conversion(self, ip_alerter):
        with pytest.raises(
            InvalidConfigurationError,
            match=r"IPv4 IP invalid_ip is invalid: Could not be converted to integer",
        ):
            ip_alerter._ip_to_int("invalid_ip", IPVersion.V4)

    @pytest.mark.parametrize(
        "test_case, event, success",
        [
            ("empty list", {"ip_field": []}, False),
            ("matches exact", {"ip_field": ["127.0.0.1"]}, True),
            ("matches network", {"ip_field": ["127.0.123.1"]}, True),
            ("no match", {"ip_field": ["111.111.111.111"]}, False),
            ("expired", {"ip_field": ["13.12.12.12"]}, False),
            ("first matches", {"ip_field": ["127.0.123.1", "111.111.111.111"]}, True),
            ("last matches", {"ip_field": ["111.111.111.111", "127.0.123.1"]}, True),
            (
                "middle matches network and last is expired",
                {"ip_field": ["111.111.111.111", "127.0.123.1", "13.12.12.12"]},
                True,
            ),
            (
                "first field matches network and last is expired",
                {"ip_field": ["127.0.123.1"], "ip_field_2": ["111.111.111.111"]},
                True,
            ),
            (
                "second field matches network and last is expired",
                {"ip_field": ["111.111.111.111"], "ip_field_2": ["127.0.123.1"]},
                True,
            ),
        ],
    )
    def test_ips_from_list_in_alerts_succeeds(
        self, ip_alerter, rule_with_fields, test_case, event, success
    ):
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event) is success

    @pytest.mark.parametrize(
        "test_case, event, expired",
        [
            (
                "source is list with matching and expired succeeds",
                {"ip_field": ["13.12.12.13", "222.222.222.222"]},
                "222.222.222.222",
            ),
            (
                "source is list with expired and matching succeeds",
                {"ip_field": ["222.222.222.222", "13.12.12.13"]},
                "222.222.222.222",
            ),
            (
                "source is list with matching and expired network succeeds",
                {"ip_field": ["127.0.0.2", "222.222.222.0/24"]},
                "222.222.222.0/24",
            ),
            (
                "source is list with expired and matching network succeeds",
                {"ip_field": ["222.222.222.0/24", "127.0.0.2"]},
                "222.222.222.0/24",
            ),
        ],
    )
    def test_ipv4_ips_from_list_and_ip_expires_during_processing_succeeds(
        self, ip_alerter, rule_with_fields, test_case, event, expired
    ):
        _add_expired_entry(ip_alerter, expired)
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)

    @pytest.mark.parametrize(
        "test_case, event, expired",
        [
            (
                "source is list with matching and expired succeeds",
                {"ip_field": ["::ffff:0d0c:0c0d", "::ffff:dede:dede"]},
                "::ffff:dede:dede",
            ),
            (
                "source is list with expired and matching succeeds",
                {"ip_field": ["::ffff:dede:dede", "::ffff:0d0c:0c0d"]},
                "::ffff:dede:dede",
            ),
            (
                "source is list with matching and expired network succeeds",
                {"ip_field": ["::2", "::ffff:dede:de00/120"]},
                "::ffff:dede:de00/120",
            ),
            (
                "source is list with expired and matching network succeeds",
                {"ip_field": ["::ffff:dede:de00/120", "::2"]},
                "::ffff:dede:de00/120",
            ),
        ],
    )
    def test_ipv6_ips_from_list_and_ip_expires_during_processing_succeeds(
        self, ip_alerter, rule_with_fields, test_case, event, expired
    ):
        _add_expired_entry(ip_alerter, expired)
        assert ip_alerter.is_in_alerts_list(rule_with_fields, event)


def _add_expired_entry(ip_alerter: IPAlerter, addr: str) -> None:
    if "/" in addr:
        ip_version = IPVersion.V6 if ":" in addr else IPVersion.V4
        ip_str, mask_str = addr.split("/")
        net_mask = ip_alerter._get_net_mask(ip_version, int(mask_str))
        network = ip_alerter._ip_to_int(ip_str, ip_version) & net_mask
        ip_alerter._expiring_cidrs[ip_version].setdefault(net_mask, {})[network] = 0.0
    else:
        ip_version = IPVersion.V6 if ":" in addr else IPVersion.V4
        parsed_addr = (
            ip_alerter._ip_to_int(addr, ip_version) if ip_version is IPVersion.V6 else addr
        )
        ip_alerter._expiring_ips[ip_version][parsed_addr] = 0.0
