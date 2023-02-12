"""
IpInformer
============

The `ip_informer` processor enriches an event with ip information.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - myipinformer:
        type: ip_informer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from functools import partial
import ipaddress
from itertools import chain
from typing import Iterable

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.ip_informer.rule import IpInformerRule
from logprep.util.helper import get_dotted_field_value


class IpInformer(FieldManager):
    """A processor that enriches ip information"""

    rule_class = IpInformerRule

    def _apply_rules(self, event: dict, rule: IpInformerRule) -> None:
        ip_address_list = self._get_ip_addresses(event, rule)
        result = {ip: self._ip_properties(ip) for ip in ip_address_list}
        self._write_target_field(event, rule, result)

    def _get_ip_addresses(self, event: dict, rule: IpInformerRule) -> Iterable:
        source_field_values = list(map(partial(get_dotted_field_value, event), rule.source_fields))
        list_elements = filter(lambda x: isinstance(x, list), source_field_values)
        str_elements = filter(lambda x: isinstance(x, str), source_field_values)
        return chain(*list_elements, str_elements)

    def _ip_properties(self, ip_address: str) -> dict[str, any]:
        ip_address = ipaddress.ip_address(ip_address)
        return {
            prop_name: getattr(ip_address, prop_name)
            for prop_name in dir(ip_address.__class__)
            if isinstance(getattr(ip_address.__class__, prop_name), property)
        }
