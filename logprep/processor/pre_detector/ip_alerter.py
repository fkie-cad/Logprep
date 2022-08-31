"""This module is used to generate alerts if an IP matches a pattern in a list."""

from typing import Union, List

from ipaddress import ip_network, ip_address, IPv4Network
from datetime import datetime
from os.path import isfile

from dateutil import parser, tz
from ruamel.yaml import YAML

from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util.helper import get_dotted_field_value

yaml = YAML(typ="safe", pure=True)


class IPAlerter:
    """Used to get if an IP is in an alert list and if the IP alert has expired."""

    def __init__(self, alert_ip_lists_path: Union[List[str], str]):
        self._alert_ips_map = {}
        self._single_alert_ips = set()
        self._alert_network = set()

        if isinstance(alert_ip_lists_path, str):
            alert_ip_lists_path = [alert_ip_lists_path]
        if not alert_ip_lists_path:
            alert_ip_lists_path = []
        self._init_alert_ip_list(alert_ip_lists_path)

    @staticmethod
    def has_ip_fields(rule: PreDetectorRule) -> bool:
        """Return if rule has IP fields."""
        return bool(rule.ip_fields)

    def _init_alert_ip_list(self, alert_ip_lists: List):
        for alert_ip_list in alert_ip_lists:
            if alert_ip_list and isfile(alert_ip_list):
                with open(alert_ip_list, "r", encoding="utf8") as alert_ip_list_file:
                    full_alert_ip_list = yaml.load(alert_ip_list_file)
                    self._filter_non_expired_alert_ips(full_alert_ip_list)
                    self._single_alert_ips.update(
                        set(ip_string for ip_string in self._alert_ips_map if "/" not in ip_string)
                    )
                    self._alert_network.update(
                        set(
                            ip_network(ip_string)
                            for ip_string in self._alert_ips_map
                            if "/" in ip_string
                        )
                    )

    def _filter_non_expired_alert_ips(self, full_alert_ip_list: dict):
        for alert_ip, expiration_date_str in full_alert_ip_list.items():
            if expiration_date_str:
                expiration_date = parser.isoparse(expiration_date_str)
                now = datetime.now(tz.UTC)
                if expiration_date > now:
                    self._alert_ips_map[alert_ip] = expiration_date_str
            else:
                self._alert_ips_map[alert_ip] = expiration_date_str

    def _single_is_not_expired(self, ip_str: str) -> bool:
        expiration_date_str = self._alert_ips_map[ip_str]
        if expiration_date_str:
            expiration_date = parser.isoparse(expiration_date_str)
            now = datetime.now(tz.UTC)
            return now < expiration_date
        return True

    def _network_is_not_expired(self, network: IPv4Network) -> bool:
        expiration_date_str = self._alert_ips_map[network.exploded]
        if expiration_date_str:
            expiration_date = parser.isoparse(expiration_date_str)
            now = datetime.now(tz.UTC)
            return now < expiration_date
        return True

    def is_in_alerts_list(self, rule: PreDetectorRule, event: dict) -> bool:
        """Check if IP is in alerts list and if the alert has expired."""
        in_alerts = False
        for field in rule.ip_fields:
            ip_string = get_dotted_field_value(event, field)
            if ip_string in self._single_alert_ips:
                in_alerts = self._single_is_not_expired(ip_string)
                continue

            try:
                ip_address_object = ip_address(ip_string)
            except ValueError:
                continue

            for network in self._alert_network:
                if ip_address_object in network:
                    in_alerts = self._network_is_not_expired(network)
                    break

        return in_alerts
