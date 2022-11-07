"""
Concatenator
============

The concatenator processor allows to concat a list of source fields into one new target field. The
separator and the target field can be specified. Furthermore, it is possible to directly delete
all given source fields, or to overwrite the specified target field.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given concatenator rule

    filter: 'date AND time'
    concatenator:
      source_fields: ["date", "time"]
      target_field: timestamp
      separator: " "
      overwrite_target: True
      delete_source_fields: True
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        "date": "01.01.1007",
        "time": "13:07"
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "timetsamp": "01.01.1007 13:07"
    }
"""
from functools import partial

from attrs import define, field, fields, validators

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.validators import min_len_validator


class ConcatenatorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for Concatenator"""

        source_fields: list = field(
            validator=[
                fields(FieldManagerRule.Config).source_fields.validator,
                partial(min_len_validator, min_length=2),
            ]
        )
        """The source fields that should be concatenated, can contain dotted field paths."""
        separator: str = field(validator=validators.instance_of(str))
        """The character(s) that should be used between the combined source field values."""

    @property
    def separator(self) -> str:  # pylint: disable=missing-docstring
        return self._config.separator
