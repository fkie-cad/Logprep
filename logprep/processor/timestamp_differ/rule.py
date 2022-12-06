"""
.. _timestamp_differ_rule:

TimestampDiffer
===============

The `timestamp_differ` processor allows to calculate the time difference between two timestamps.
The timestamp format can be specified per timestamp. Following patterns can be used to define the
timestamp format:
`Timestamp tokens <https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens>`_.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given timestamp differ rule

    filter: 'ingest AND processed'
    timestamp_differ:
      diff: ${processed:YYYY-MM-DD HH:MM:SS} - ${ingest:YYYY-MM-DD HH:MM:SS}
      target_field: processing_time
      output_format: seconds
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"ingest": "2022-12-06 10:00:00", "processed": "2022-12-06 10:00:05"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {"ingest": "2022-12-06 10:00:00", "processed": "2022-12-06 10:00:05", "processing_time": "5 s"}
"""
import re

from attr import field
from attrs import define, validators

from logprep.processor.field_manager.rule import FieldManagerRule

FIELD_PATTERN = r"\$\{([+&?]?[^${]*)\}"
DEFAULT_TIMESTAMP_PATTERN = "YYYY-MM-DDTHH:mm:ssZZ"


class TimestampDifferRule(FieldManagerRule):
    """TimestampDifferRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for TimestampDiffer"""

        diff: str = field(
            validator=[
                validators.instance_of(str),
                validators.matches_re(rf"({FIELD_PATTERN} - {FIELD_PATTERN})"),
            ]
        )
        """Specifies the timestamp subtraction and their respective timestamp formats. The fields
        and the timestamp format can be specified in the form of:
        :code:`${dotted.field.path:timestamp-format}`. If no timestamp format is given, e.g.
        :code:`${dotted.field.path}`, then the default pattern :code:`"YYYY-MM-DDTHH:mm:ssZZ"` will
        be used."""
        source_fields: list = field(factory=list)
        output_format: str = field(
            default="seconds",
            validator=[
                validators.instance_of(str),
                validators.in_(["seconds", "milliseconds", "nanoseconds"]),
            ],
        )
        """(Optional) Specifies the desired output format of the timestamp difference, allowed
        values are: :code:`seconds`, :code:`milliseconds`, :code:`nanoseconds`, defaults to:
        :code:`seconds`."""

        def __attrs_post_init__(self):
            field_format_str = re.findall(FIELD_PATTERN, self.diff)
            field_format_tuple = map(lambda s: s.split(":", maxsplit=1), field_format_str)
            field_format_tuple = map(
                lambda x: x + [DEFAULT_TIMESTAMP_PATTERN] if len(x) == 1 else x, field_format_tuple
            )
            self.source_fields = list(field_format_tuple)

    # pylint: disable=missing-function-docstring
    @property
    def diff(self):
        return self._config.diff

    @property
    def output_format(self):
        return self._config.output_format

    # pylint: enable=missing-function-docstring
