"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

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

.. autoclass:: logprep.processor.concatenator.rule.ConcatenatorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attrs import define, field, fields, validators

from logprep.processor.field_manager.rule import FieldManagerRule


class ConcatenatorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for Concatenator"""

        source_fields: list = field(
            validator=[
                fields(FieldManagerRule.Config).source_fields.validator,
                validators.min_len(2),
            ]
        )
        """The source fields that should be concatenated, can contain dotted field paths."""
        separator: str = field(validator=validators.instance_of(str))
        """The character(s) that should be used between the combined source field values."""
        mapping: dict = field(default="", init=False, repr=False, eq=False)

    @property
    def separator(self) -> str:  # pylint: disable=missing-docstring
        return self._config.separator
