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
      diff: ${processed:YYYY-MM-DD HH:mm:ss} - ${ingest:YYYY-MM-DD HH:mm:ss}
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

    {"ingest": "2022-12-06 10:00:00", "processed": "2022-12-06 10:00:05", "processing_time": "5.0"}

Examples for timestamp_differ:
------------------------------

.. datatemplate:import-module:: tests.unit.processor.timestamp_differ.test_timestamp_differ
   :template: testcase-renderer.tmpl
"""
import re

from attr import field
from attrs import define, validators

from logprep.processor.field_manager.rule import FieldManagerRule, FIELD_PATTERN


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
        :code:`${dotted.field.path}`, then the default parsing mechanism of the python library
        arrow will be used. For more information see the
        `Arrow documentation <https://arrow.readthedocs.io/en/latest/guide.html#creation>`_."""
        source_fields: list = field(factory=list)
        source_field_formats: list = field(factory=list)
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
        show_unit: bool = field(default=False)
        """(Optional) Specifies whether the unit (s, ms, ns) should be part of the output.
        Defaults to :code:`False`."""

        def __attrs_post_init__(self):
            field_format_str = re.findall(FIELD_PATTERN, self.diff)
            field_format_tuple = map(lambda s: s.split(":", maxsplit=1), field_format_str)
            field_format_tuple = map(lambda x: x + [None] if len(x) == 1 else x, field_format_tuple)
            source_fields, source_field_formats = list(map(list, zip(*field_format_tuple)))
            self.source_fields = source_fields
            self.source_field_formats = source_field_formats

    # pylint: disable=missing-function-docstring
    @property
    def output_format(self):
        return self._config.output_format

    @property
    def source_field_formats(self):
        return self._config.source_field_formats

    @property
    def show_unit(self):
        return self._config.show_unit

    # pylint: enable=missing-function-docstring
