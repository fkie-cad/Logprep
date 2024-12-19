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
        rules:
            - tests/testdata/rules/rules


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
from logprep.util.time import TimeParser, TimeParserException


class Timestamper(FieldManager):
    """A processor that extracts and parses timestamps"""

    rule_class = TimestamperRule

    def _apply_rules(self, event, rule):
        source_value = get_dotted_field_value(event, rule.source_fields[0])
        if self._handle_missing_fields(event, rule, rule.source_fields, [source_value]):
            return

        source_timezone, target_timezone, source_formats = (
            rule.source_timezone,
            rule.target_timezone,
            rule.source_format,
        )
        parsed_successfully = False
        for source_format in source_formats:
            try:
                parsed_datetime = TimeParser.parse_datetime(
                    source_value, source_format, source_timezone
                )
            except TimeParserException:
                continue
            result = parsed_datetime.astimezone(target_timezone).isoformat().replace("+00:00", "Z")
            self._write_target_field(event, rule, result)
            parsed_successfully = True
            break
        if not parsed_successfully:
            raise ProcessingWarning(str("Could not parse timestamp"), rule, event)
