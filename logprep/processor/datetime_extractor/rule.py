"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

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

.. autoclass:: logprep.processor.datetime_extractor.rule.DatetimeExtractorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attr import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule


class DatetimeExtractorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for DatetimeExtractorRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.max_len(1),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
        )
        """The fields from where to get the values which should be processed."""
        target_field: str = field(validator=validators.instance_of(str))
        """The field where to write the processed values to. """
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
