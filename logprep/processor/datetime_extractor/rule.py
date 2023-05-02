"""
Datetime Extractor
==================

The datetime extractor requires the additional field :code:`datetime_extractor`.
The additional fields :code:`datetime_extractor.source_fields` and
:code:`datetime_extractor.target_field` must be defined.
The first one contains the name of the field from which the timestamp should be taken
and the last one contains the name of the field under which a split timestamp should be written.

In the following example the timestamp will be extracted from
:code:`@timestamp` and written to :code:`split_@timestamp`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: '@timestamp'
    datetime_extractor:
      source_fields: ['@timestamp']
      target_field: 'split_@timestamp'
    description: '...'
"""
from logprep.processor.field_manager.rule import FieldManagerRule


class DatetimeExtractorRule(FieldManagerRule):
    """Check if documents match a filter."""
