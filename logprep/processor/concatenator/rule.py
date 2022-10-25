"""
Concatenator Rule
-----------------

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

from attrs import define, field, validators

from logprep.processor.base.rule import Rule
from logprep.util.validators import min_len_validator


class ConcatenatorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Concatenator"""

        source_fields: list = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.instance_of(list),
                ),
                partial(min_len_validator, min_length=2),
            ]
        )
        """The source fields that should be concatenated, can contain dotted field paths."""
        target_field: str = field(validator=validators.instance_of(str))
        """The field in which the result should be written to."""
        separator: str = field(validator=validators.instance_of(str))
        """The character(s) that should be used between the combined source field values."""
        overwrite_target: bool = field(validator=validators.instance_of(bool))
        """Defines whether the target field should be overwritten if it exists already."""
        delete_source_fields: bool = field(validator=validators.instance_of(bool))
        """Defines whether the source fields should be deleted after they have been combined
        to the new field."""

    _config: "ConcatenatorRule.Config"

    @property
    def source_fields(self) -> list:  # pylint: disable=missing-docstring
        return self._config.source_fields

    @property
    def target_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.target_field

    @property
    def separator(self) -> str:  # pylint: disable=missing-docstring
        return self._config.separator

    @property
    def overwrite_target(self) -> bool:  # pylint: disable=missing-docstring
        return self._config.overwrite_target

    @property
    def delete_source_fields(self) -> bool:  # pylint: disable=missing-docstring
        return self._config.delete_source_fields
