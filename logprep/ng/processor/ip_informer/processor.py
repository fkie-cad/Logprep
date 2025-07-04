"""
IpInformer
==========

The `ip_informer` processor enriches an event with ip information.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - myipinformer:
        type: ip_informer
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.ip_informer.processor.IpInformer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.ip_informer.rule
"""

import ipaddress
from functools import partial
from itertools import chain
from typing import Iterable

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.ip_informer.rule import IpInformerRule, get_ip_property_names
from logprep.util.helper import get_dotted_field_value


class IpInformer(FieldManager):
    """A processor that enriches ip information"""

    __slots__ = ("_processing_warnings",)

    _processing_warnings: list[tuple[str, Exception]]

    rule_class = IpInformerRule

    def _apply_rules(self, event: dict, rule: IpInformerRule) -> None:
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, rule.source_fields, source_field_values)
        self._processing_warnings = []
        ip_address_list = self._get_flat_ip_address_list(event, rule)
        results = self._get_results(ip_address_list, rule)
        if results:
            self._write_target_field(event, rule, results)
        for msg, error in self._processing_warnings:
            raise ProcessingWarning(msg, rule, event) from error

    def _get_results(self, ip_address_list: Iterable, rule: IpInformerRule) -> dict:
        results = [(ip, self._ip_properties(ip, rule)) for ip in ip_address_list]
        return dict(filter(lambda x: bool(x[1]), results))

    def _get_flat_ip_address_list(self, event: dict, rule: IpInformerRule) -> Iterable:
        source_field_values = list(map(partial(get_dotted_field_value, event), rule.source_fields))
        list_elements = filter(lambda x: isinstance(x, list), source_field_values)
        str_elements = filter(lambda x: isinstance(x, str), source_field_values)
        return chain(*list_elements, str_elements)

    def _ip_properties(self, ip_address: str, rule: IpInformerRule) -> dict[str, any]:
        try:
            ip_address = ipaddress.ip_address(ip_address)
        except ValueError as error:
            self._processing_warnings.append(
                (f"({self.name}): '{ip_address}' is not a valid IPAddress", error)
            )
        properties = rule.properties
        if "default" in properties:
            return {
                prop_name: getattr(ip_address, prop_name)
                for prop_name in get_ip_property_names(ip_address.__class__)
            }
        return {prop_name: getattr(ip_address, prop_name, False) for prop_name in rule.properties}
