"""This module is used to generate alerts if an IP matches a pattern in a list."""

import time
from enum import Enum, auto
from socket import inet_aton, inet_pton, AF_INET6
from os.path import isfile

from logprep.factory_error import InvalidConfigurationError
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser


class IPVersion(Enum):
    """Used to denote which IP version is being used"""

    V4 = auto()
    V6 = auto()


class IPAlerter:
    """Used to get if an IP is in an alert list and if the IP alert has expired."""

    _IP_MASKS = {
        IPVersion.V4: 0xFFFFFFFF,  # 32 bits
        IPVersion.V6: 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,  # 128 bits
    }

    def __init__(self, address_mapping_paths: list[str] | str | None):
        self._convert_ip_to_int_methods = {
            IPVersion.V4: self._convert_ipv4_to_int,
            IPVersion.V6: self._convert_ipv6_to_int,
        }
        self._permanent_ips: dict[IPVersion, set[str | int]] = {v: set() for v in IPVersion}
        self._expiring_ips: dict[IPVersion, dict[str | int, float]] = {v: {} for v in IPVersion}

        self._permanent_cidrs: dict[IPVersion, dict[int, set[int]]] = {v: {} for v in IPVersion}
        self._expiring_cidrs: dict[IPVersion, dict[int, dict[int, float]]] = {
            v: {} for v in IPVersion
        }
        self._init_address_lists(self._normalize_paths(address_mapping_paths))

    @staticmethod
    def _normalize_paths(paths: str | list[str] | None) -> list[str]:
        """Convert the input paths into a flat list of paths."""
        if paths is None:
            return []
        if isinstance(paths, str):
            return [paths]
        return paths

    @staticmethod
    def has_ip_fields(rule: PreDetectorRule) -> bool:
        """Return if rule has IP fields."""
        return bool(rule.ip_fields)

    def _init_address_lists(self, address_mapping_paths: list[str]):
        for mapping_path in address_mapping_paths:
            if not isfile(mapping_path):
                raise InvalidConfigurationError(f"Mapping file does not exist: {mapping_path}")
            address_mapping = GetterFactory.from_string(mapping_path).get_yaml()
            if isinstance(address_mapping, list):
                raise ValueError(f"expected a mapping and not a list ({mapping_path})")
            self._add_address_mapping(address_mapping)

    def _add_address_mapping(self, address_mapping: dict):
        """Add addresses to mapping, skipping expired addresses."""
        now = time.time()
        for addr, expiration_str in address_mapping.items():
            if not expiration_str:
                # Has no expiration date, set None to add into permanent mapping later
                expiration_time = None
            else:
                expiration_time = TimeParser.from_string(expiration_str).timestamp()
                if expiration_time <= now:
                    # Will not be added to mapping, since it has expired
                    continue
            self._add_address(addr, expiration_time)

    def _add_address(self, addr: str, expiration_time: float | None):
        if "/" in addr:
            version = IPVersion.V4 if ":" not in addr else IPVersion.V6
            self._add_cidr(addr, version, expiration_time)
        elif ":" in addr:
            ip_int = self._ip_to_int(addr, IPVersion.V6)
            self._add_ip(ip_int, IPVersion.V6, expiration_time)
        else:
            self._add_ip(addr, IPVersion.V4, expiration_time)

    def _add_ip(self, ip: str | int, ip_version: IPVersion, expiration_time: float | None):
        if expiration_time is None:
            self._permanent_ips[ip_version].add(ip)
        else:
            self._expiring_ips[ip_version][ip] = expiration_time

    def _add_cidr(self, cidr_string: str, ip_version: IPVersion, expiration_time: float | None):
        ip_str, mask_str = cidr_string.split("/")
        mask_len = int(mask_str)
        ip_bit_mask_len = self._IP_MASKS[ip_version].bit_length()
        if not (0 <= mask_len <= ip_bit_mask_len):
            raise InvalidConfigurationError(
                f"IP{ip_version.name.lower()} CIDR mask invalid for {cidr_string}"
            )
        net_mask = self._get_net_mask(ip_version, mask_len)
        network = self._ip_to_int(ip_str, ip_version) & net_mask
        if expiration_time is None:
            self._permanent_cidrs[ip_version].setdefault(net_mask, set()).add(network)
        else:
            self._expiring_cidrs[ip_version].setdefault(net_mask, {})[network] = expiration_time

    @staticmethod
    def _get_net_mask(ip_version: IPVersion, mask_len: int) -> int:
        ip_bit_mask = IPAlerter._IP_MASKS[ip_version]
        ip_bit_mask_len = ip_bit_mask.bit_length()
        return ip_bit_mask << (ip_bit_mask_len - mask_len) & ip_bit_mask

    def is_in_alerts_list(self, rule: PreDetectorRule, event: dict) -> bool:
        """Check if IP is in alerts list and if the alert has expired."""
        for field in rule.ip_fields:
            ip_or_ips = get_dotted_field_value(event, field)
            ips = ip_or_ips if isinstance(ip_or_ips, list) else (ip_or_ips,)
            for ip_string in ips:
                if isinstance(ip_string, str) and self._ip_is_in_alert_list(ip_string):
                    return True
        return False

    def _ip_is_in_alert_list(self, ip_str: str) -> bool:
        ip_version = IPVersion.V6 if ":" in ip_str else IPVersion.V4
        return self._ip_in_ip_set(ip_str, ip_version) or self._ip_in_cidr_index(ip_str, ip_version)

    def _ip_in_ip_set(self, ip_str: str, ip_version: IPVersion) -> bool:
        if ip_version is IPVersion.V4:
            ip = ip_str
        else:
            try:
                ip = self._convert_ipv6_to_int(ip_str)
            except OSError:
                return False
        if ip in self._permanent_ips[ip_version]:
            return True
        expiration_time = self._expiring_ips[ip_version].get(ip)
        return expiration_time is not None and expiration_time > time.time()

    def _ip_in_cidr_index(self, ip_str: str, ip_version: IPVersion) -> bool:
        """Return whether ``ip_str`` falls inside of CIDR for ``ip_version``.

        A match is only reported when the corresponding IP has not yet expired.
        CIDR ranges are stored grouped by their precomputed network mask,
        so this performs one check per prefix length rather than checking all CIDR entries.
        """
        permanent_cidrs_grouped_by_mask = self._permanent_cidrs[ip_version]
        expiring_cidrs_grouped_by_mask = self._expiring_cidrs[ip_version]
        if not permanent_cidrs_grouped_by_mask and not expiring_cidrs_grouped_by_mask:
            return False
        try:
            ip_int = self._convert_ip_to_int_methods[ip_version](ip_str)
        except OSError:
            return False
        now = time.time()
        for net_mask, networks in permanent_cidrs_grouped_by_mask.items():
            if (ip_int & net_mask) in networks:
                return True
        for net_mask, net_mapping in expiring_cidrs_grouped_by_mask.items():
            expiration_time = net_mapping.get(ip_int & net_mask)
            if expiration_time is not None and expiration_time > now:
                return True
        return False

    def _ip_to_int(self, ip: str, ip_version: IPVersion) -> int:
        try:
            return self._convert_ip_to_int_methods[ip_version](ip)
        except OSError as error:
            raise InvalidConfigurationError(
                f"IP{ip_version.name.lower()} IP {ip} is invalid: Could not be converted to integer"
            ) from error

    @staticmethod
    def _convert_ipv4_to_int(ip_string: str):
        return int.from_bytes(inet_aton(ip_string), byteorder="big")

    @staticmethod
    def _convert_ipv6_to_int(ip_string: str):
        return int.from_bytes(inet_pton(AF_INET6, ip_string), byteorder="big")
