"""
|PROCESSOR_NAME|
================

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
import typing
from functools import partial
from itertools import chain
from typing import Iterable

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.base.rule import Rule
from logprep.processor.ip_informer.rule import IpInformerRule, get_ip_property_names
from logprep.util.helper import (
    FieldValue,
    get_dotted_field_value,
    get_dotted_field_values,
)


class IpInformer(FieldManager):
    """A processor that enriches ip information"""

    __slots__ = ("_processing_warnings",)

    _processing_warnings: list[tuple[str, Exception]]

    rule_class = IpInformerRule

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        rule = typing.cast(IpInformerRule, rule)
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

    def _get_flat_ip_address_list(
        self, event: dict[str, FieldValue], rule: IpInformerRule
    ) -> Iterable:
        source_field_values = list(get_dotted_field_values(event, rule.source_fields).values())
        list_elements = [value for value in source_field_values if isinstance(value, list)]
        str_elements = [value for value in source_field_values if isinstance(value, str)]

        return chain(*list_elements, str_elements)

    def _ip_properties(self, ip_address: str, rule: IpInformerRule) -> dict:
        try:
            ip_address_res = ipaddress.ip_address(ip_address)
        except ValueError as error:
            self._processing_warnings.append(
                (f"({self.name}): '{ip_address}' is not a valid IPAddress", error)
            )
            return {}

        properties = rule.properties
        if "default" in properties:
            return {
                prop_name: getattr(ip_address_res, prop_name)
                for prop_name in get_ip_property_names(ip_address_res.__class__)
            }
        return {
            prop_name: getattr(ip_address_res, prop_name, False) for prop_name in rule.properties
        }
