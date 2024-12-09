"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The timestamp format can be specified per timestamp.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given timestamp differ rule

    filter: 'ingest AND processed'
    timestamp_differ:
      diff: ${processed:%Y-%m-%d %H:%M:%S} - ${ingest:%Y-%m-%d %H:%M:%S}
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

.. autoclass:: logprep.processor.timestamp_differ.rule.TimestampDifferRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for timestamp_differ:
------------------------------

.. datatemplate:import-module:: tests.unit.processor.timestamp_differ.test_timestamp_differ
   :template: testcase-renderer.tmpl
"""

import re

from attr import field
from attrs import define, validators

from logprep.processor.field_manager.rule import FIELD_PATTERN, FieldManagerRule


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
        :code:`${dotted.field.path}`, the string will be assumed as an iso8601 compliant string and
        parsed. For more information on the format syntax see `datetime strftime/strptime
        <https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes>`_."""
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
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

        def __attrs_post_init__(self):
            field_format_str = re.findall(FIELD_PATTERN, self.diff)
            field_format_tuple = map(lambda s: s.split(":", maxsplit=1), field_format_str)
            field_format_tuple = map(lambda x: x + [None] if len(x) == 1 else x, field_format_tuple)
            source_fields, source_field_formats = list(map(list, zip(*field_format_tuple)))
            self.source_fields = source_fields
            self.source_field_formats = source_field_formats
            super().__attrs_post_init__()

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
