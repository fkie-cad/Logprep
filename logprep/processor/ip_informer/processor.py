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
from typing import Dict, Iterable, List, Tuple
from logprep.processor.base.exceptions import ProcessingWarning

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.ip_informer.rule import IpInformerRule
from logprep.util.helper import get_dotted_field_value


class IpInformer(FieldManager):
    """A processor that enriches ip information"""

    __slots__ = ("_processing_warnings",)

    _processing_warnings: List[Tuple[str, Exception]]

    rule_class = IpInformerRule

    def _apply_rules(self, event: Dict, rule: IpInformerRule) -> None:
        self._processing_warnings = []
        ip_address_list = self._get_flat_ip_address_list(event, rule)
        results = self._get_results(ip_address_list)
        if results:
            self._write_target_field(event, rule, results)
        for msg, error in self._processing_warnings:
            raise ProcessingWarning(msg) from error

    def _get_results(self, ip_address_list: Iterable) -> Dict:
        results = [(ip, self._ip_properties(ip)) for ip in ip_address_list]
        return dict(filter(lambda x: bool(x[1]), results))

    def _get_flat_ip_address_list(self, event: Dict, rule: IpInformerRule) -> Iterable:
        source_field_values = list(map(partial(get_dotted_field_value, event), rule.source_fields))
        list_elements = filter(lambda x: isinstance(x, list), source_field_values)
        str_elements = filter(lambda x: isinstance(x, str), source_field_values)
        return chain(*list_elements, str_elements)

    def _ip_properties(self, ip_address: str) -> Dict[str, any]:
        try:
            ip_address = ipaddress.ip_address(ip_address)
        except ValueError as error:
            self._processing_warnings.append(
                (f"({self.name}): '{ip_address}' is not a valid IPAddress", error)
            )
        return {
            prop_name: getattr(ip_address, prop_name)
            for prop_name in filter(lambda x: x != "packed", dir(ip_address.__class__))
            if isinstance(getattr(ip_address.__class__, prop_name), property)
        }  # we have to remove the property `packed` because it is not json serializable
