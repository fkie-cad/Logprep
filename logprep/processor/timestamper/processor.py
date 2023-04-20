"""
Timestamper
============

The `timestamper` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: timestamper
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from attrs import define, field, validators

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.timestamper.rule import TimestamperRule


class Timestamper(FieldManager):
    """A processor that ..."""

    rule_class = TimestamperRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """ Config of ..."""
        ...

    def _apply_rules(self, event, rule):
        pass