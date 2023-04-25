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

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.timestamper.rule import TimestamperRule
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser, TimeParserException


class Timestamper(FieldManager):
    """A processor that extracts and parses timestamps"""

    rule_class = TimestamperRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config of Timestamper"""

    def _apply_rules(self, event, rule):
        source_field = self._get_source_field(event, rule)
        source_timezone, target_timezone, source_format = (
            rule.source_timezone,
            rule.target_timezone,
            rule.source_format,
        )
        try:
            parsed_datetime = self._parse_datetime(source_field, source_format, source_timezone)
        except TimeParserException as error:
            raise ProcessingWarning(self, str(error), rule, event) from error
        result = parsed_datetime.astimezone(target_timezone).isoformat().replace("+00:00", "Z")
        self._write_target_field(event, rule, result)

    def _get_source_field(self, event, rule):
        source_field = rule.source_fields[0]
        source_field_value = get_dotted_field_value(event, source_field)
        if not source_field_value:
            raise ProcessingWarning(
                self, f"'{source_field}' does not exist or is falsy value", rule, event
            )

        return source_field_value

    def _parse_datetime(self, source_field, source_format, source_timezone):
        if source_format == "ISO8601":
            parsed_datetime = TimeParser.from_string(source_field).astimezone(source_timezone)
        elif source_format == "UNIX":
            parsed_datetime = (
                int(source_field) if len(source_field) <= 10 else int(source_field) / 1000
            )
            parsed_datetime = TimeParser.from_timestamp(parsed_datetime).astimezone(source_timezone)
        else:
            parsed_datetime = TimeParser.from_format(source_field, source_format).astimezone(
                source_timezone
            )

        return parsed_datetime
