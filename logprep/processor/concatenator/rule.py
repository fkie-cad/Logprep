"""
Concatenator Rule
-----------------

The concatenator processor allows to concat a list of source fields into one new target field. The
seperator and the target field can be specified. Furthermore, it is possible to directly delete
all given source fields, or to overwrite the specified target field.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given concatenator rule

    filter: 'date AND time'
    concatenator:
      source_fields: ["date", "time"]
      target_field: timestamp
      seperator: " "
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
from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import InvalidRuleDefinitionError, Rule


class ConcatenatorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config:
        """RuleConfig for Concatenator"""

        source_fields: list = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(str),
                iterable_validator=validators.instance_of(list),
            )
        )
        """The source fields that should be concatenated, can contain dotted field paths."""
        target_field: str = field(validator=validators.instance_of(str))
        """The field in which the result should be written to."""
        seperator: str = field(validator=validators.instance_of(str))
        """The character(s) that should be used between the combined source field values."""
        overwrite_target: bool = field(validator=validators.instance_of(bool))
        """Defines whether the target field should be overwritten if it exists already."""
        delete_source_fields: bool = field(validator=validators.instance_of(bool))
        """Defines whether the source fields should be deleted after they have been combined
        to the new field."""

    _config: "ConcatenatorRule.Config"

    def __init__(self, filter_rule: FilterExpression, config: "ConcatenatorRule.Config"):
        """
        Instantiate ConcatenatorRule based on a given filter and processor configuration.

        Parameters
        ----------
        filter_rule : FilterExpression
            Given lucene filter expression as a representation of the rule's logic.
        config : "ConcatenatorRule.Config"
            Configuration fields from a given pipeline that refer to the processor instance.
        """
        super().__init__(filter_rule)
        self._config = config

    def __eq__(self, other: "ConcatenatorRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                self.source_fields == other.source_fields,
                self.target_field == other.target_field,
                self.seperator == other.seperator,
                self.overwrite_target == other.overwrite_target,
                self.delete_source_fields == other.delete_source_fields,
            ]
        )

    @property
    def source_fields(self) -> list:  # pylint: disable=missing-docstring
        return self._config.source_fields

    @property
    def target_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.target_field

    @property
    def seperator(self) -> str:  # pylint: disable=missing-docstring
        return self._config.seperator

    @property
    def overwrite_target(self) -> bool:  # pylint: disable=missing-docstring
        return self._config.overwrite_target

    @property
    def delete_source_fields(self) -> bool:  # pylint: disable=missing-docstring
        return self._config.delete_source_fields

    @staticmethod
    def _create_from_dict(rule: dict) -> "ConcatenatorRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("concatenator")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = ConcatenatorRule.Config(**config)
        return ConcatenatorRule(filter_expression, config)
