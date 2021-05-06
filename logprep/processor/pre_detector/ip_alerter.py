from typing import Union, Optional
from logprep.processor.pre_detector.rule import PreDetectorRule

from ipaddress import ip_network, ip_address, IPv4Network
from datetime import datetime
from os.path import isfile

from dateutil import parser, tz
from ruamel.yaml import safe_load


class IPAlerter:
    def __init__(self, alert_ip_list_path: str):
        self._alert_ips_map = dict()
        self._single_alert_ips = set()
        self._alert_network = set()

        self._init_alert_ip_list(alert_ip_list_path)

    @staticmethod
    def has_ip_fields(rule: PreDetectorRule) -> bool:
        return bool(rule.ip_fields)

    def _init_alert_ip_list(self, alert_ip_list: str):
        if alert_ip_list and isfile(alert_ip_list):
            with open(alert_ip_list, 'r') as alert_ip_list_file:
                full_alert_ip_list = safe_load(alert_ip_list_file)
                self._filter_non_expired_alert_ips(full_alert_ip_list)
                self._single_alert_ips = set(ip for ip in self._alert_ips_map.keys() if '/' not in ip)
                self._alert_network = set(ip_network(ip) for ip in self._alert_ips_map.keys() if '/' in ip)

    def _filter_non_expired_alert_ips(self, full_alert_ip_list: dict):
        for alert_ip, expiration_date_str in full_alert_ip_list.items():
            if expiration_date_str:
                expiration_date = parser.isoparse(expiration_date_str)
                now = datetime.now(tz.UTC)
                if expiration_date > now:
                    self._alert_ips_map[alert_ip] = expiration_date_str
            else:
                self._alert_ips_map[alert_ip] = expiration_date_str

    def _single_is_not_expired(self, ip: str) -> bool:
        expiration_date_str = self._alert_ips_map[ip]
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

    @staticmethod
    def _get_dotted_field_value(dotted_field: str, event: dict) -> Optional[Union[dict, list, str]]:
        fields = dotted_field.split('.')
        dict_ = event
        for field in fields:
            if field in dict_:
                dict_ = dict_[field]
            else:
                return None
        return dict_

    def is_in_alerts_list(self, rule: PreDetectorRule, event: dict) -> bool:
        in_alerts = False
        for field in rule.ip_fields:
            ip = self._get_dotted_field_value(field, event)
            if ip in self._single_alert_ips:
                in_alerts = self._single_is_not_expired(ip)
                continue

            try:
                ip_address_object = ip_address(ip)
            except ValueError:
                continue

            for network in self._alert_network:
                if ip_address_object in network:
                    in_alerts = self._network_is_not_expired(network)
                    break

        return in_alerts

