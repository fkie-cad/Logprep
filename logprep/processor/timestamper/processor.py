"""
Timestamper
===========

The `timestamper` processor normalizes timestamps to *iso8601* compliant output format.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - myteimestamper:
        type: timestamper
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/


.. autoclass:: logprep.processor.timestamper.processor.Timestamper.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.timestamper.rule
"""

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.timestamper.rule import TimestamperRule
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParserException, TimeParser


class Timestamper(FieldManager):
    """A processor that extracts and parses timestamps"""

    rule_class = TimestamperRule

    def _apply_rules(self, event, rule):
        source_field = self._get_source_field(event, rule)
        source_timezone, target_timezone, source_formats = (
            rule.source_timezone,
            rule.target_timezone,
            rule.source_format,
        )
        parsed_successfully = False
        for source_format in source_formats:
            try:
                parsed_datetime = TimeParser.parse_datetime(
                    source_field, source_format, source_timezone
                )
            except TimeParserException:
                continue
            result = parsed_datetime.astimezone(target_timezone).isoformat().replace("+00:00", "Z")
            self._write_target_field(event, rule, result)
            parsed_successfully = True
            break
        if not parsed_successfully:
            raise ProcessingWarning(str("Could not parse timestamp"), rule, event)

    def _get_source_field(self, event, rule):
        source_field = rule.source_fields[0]
        source_field_value = get_dotted_field_value(event, source_field)
        if not source_field_value:
            raise ProcessingWarning(
                f"'{source_field}' does not exist or is falsy value", rule, event
            )

        return source_field_value
