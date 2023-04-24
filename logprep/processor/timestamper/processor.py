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
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser


class Timestamper(FieldManager):
    """A processor that extracts and parses timestamps"""

    rule_class = TimestamperRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config of Timestamper"""

    def _apply_rules(self, event, rule):
        source_field = get_dotted_field_value(event, rule.source_fields[0])
        parsed_datetime = TimeParser.from_string(source_field)
        self._write_target_field(event, rule, parsed_datetime.isoformat())
