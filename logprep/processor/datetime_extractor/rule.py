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
import warnings
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DatetimeExtractorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""
        if rule.get("datetime_extractor", {}).get("datetime_field") is not None:
            source_field_value = pop_dotted_field_value(rule, "datetime_extractor.datetime_field")
            add_and_overwrite(rule, "datetime_extractor.source_fields", [source_field_value])
            warnings.warn(
                (
                    "datetime_extractor.datetime_field is deprecated. "
                    "Use datetime_extractor.source_fields instead"
                ),
                DeprecationWarning,
            )
        if rule.get("datetime_extractor", {}).get("destination_field") is not None:
            target_field_value = pop_dotted_field_value(
                rule, "datetime_extractor.destination_field"
            )
            add_and_overwrite(rule, "datetime_extractor.target_field", target_field_value)
            warnings.warn(
                (
                    "datetime_extractor.destination_field is deprecated. "
                    "Use datetime_extractor.target_field instead"
                ),
                DeprecationWarning,
            )
