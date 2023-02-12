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
import ipaddress

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.ip_informer.rule import IpInformerRule
from logprep.util.helper import get_source_fields_dict


class IpInformer(FieldManager):
    """A processor that enriches ip information"""

    rule_class = IpInformerRule

    def _apply_rules(self, event: dict, rule: IpInformerRule) -> None:
        source_field_dict = get_source_fields_dict(event, rule)
        result = {ip: self._ip_properties(ip) for _, ip in source_field_dict.items()}
        self._write_target_field(event, rule, result)

    def _ip_properties(self, ip_address: str) -> dict[str, any]:
        ip_address = ipaddress.ip_address(ip_address)
        return {
            prop_name: getattr(ip_address, prop_name)
            for prop_name in dir(ip_address.__class__)
            if isinstance(getattr(ip_address.__class__, prop_name), property)
        }
