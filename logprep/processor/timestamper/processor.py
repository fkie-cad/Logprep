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
from zoneinfo import ZoneInfo

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
        source_format = rule.source_format
        source_timezone, target_timezone = rule.source_timezone, rule.target_timezone
        if source_format == "ISO8601":
            parsed_datetime = TimeParser.from_string(source_field).astimezone(source_timezone)
        elif source_format == "UNIX":
            parsed_datetime = (
                int(source_field) if len(source_field) < 10 else int(source_field) / 1000
            )
            parsed_datetime = TimeParser.from_timestamp(parsed_datetime).astimezone(source_timezone)
        else:
            parsed_datetime = TimeParser.from_format(source_field, source_format).astimezone(
                source_timezone
            )
        self._write_target_field(
            event,
            rule,
            parsed_datetime.astimezone(target_timezone).isoformat().replace("+00:00", "Z"),
        )
