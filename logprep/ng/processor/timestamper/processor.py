"""
|PROCESSOR_NAME|
================

The `timestamper` processor normalizes timestamps to *iso8601* compliant output format.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - myteimestamper:
        type: timestamper
        rules:
            - tests/testdata/rules/rules


.. autoclass:: logprep.processor.timestamper.processor.Timestamper.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.timestamper.rule
"""

import datetime
import typing

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.base.rule import Rule
from logprep.processor.timestamper.rule import TimestamperRule
from logprep.util.helper import FieldValue, get_dotted_field_value
from logprep.util.time import TimeParser, TimeParserException


class Timestamper(FieldManager):
    """A processor that extracts and parses timestamps"""

    rule_class = TimestamperRule

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        rule = typing.cast(TimestamperRule, rule)

        parsed_datetime = self._get_datetime(event, rule)
        if parsed_datetime is None:
            return

        result = parsed_datetime.astimezone(rule.target_timezone).isoformat().replace("+00:00", "Z")
        self._write_target_field(event, rule, result)

    def _get_datetime(
        self,
        event: dict[str, FieldValue],
        rule: TimestamperRule,
    ) -> datetime.datetime | None:
        """Return the datetime to use for timestamp generation

        If no source field is configured, the current time is used
        """
        if not rule.source_fields:
            return TimeParser.now(rule.target_timezone)

        source_value = get_dotted_field_value(event, rule.source_fields[0])
        if self._handle_missing_fields(event, rule, rule.source_fields, [source_value]):
            return None

        return self._parse_datetime(str(source_value), event, rule)

    @staticmethod
    def _parse_datetime(
        source_value: str,
        event: dict[str, FieldValue],
        rule: TimestamperRule,
    ) -> datetime.datetime:
        """Parse a timestamp value according to the configured source formats"""
        for source_format in rule.source_format:
            try:
                return TimeParser.parse_datetime(
                    source_value,
                    source_format,
                    rule.source_timezone,
                )
            except TimeParserException:
                continue

        raise ProcessingWarning("Could not parse timestamp", rule, event)
