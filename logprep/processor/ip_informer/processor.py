"""
IpInformer
============

The `ip_informer` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: ip_informer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from attrs import define, field, validators

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.ip_informer.rule import IpInformerRule



class IpInformer(FieldManager):
    """A processor that ..."""

    rule_class = IpInformerRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        ...

    def _apply_rules(self, event, rule):
        ...