"""
This module defines the rule for the concatenator processor which enables combining multiple source
fields to one target field
"""

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import InvalidRuleDefinitionError, Rule

yaml = YAML(typ="safe", pure=True)


class ConcatenatorRuleError(InvalidRuleDefinitionError):
    """Base class for Concatenator rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"Concatenator rule ({message})")


class InvalidConcatenatorRuleDefinition(ConcatenatorRuleError):
    """Raise if ConcatenatorRule definition invalid."""

    def __init__(self, definition):
        message = f"The following Concatenator definition is invalid: {definition}"
        super().__init__(message)


class ConcatenatorRule(Rule):
    """Check if documents match a filter."""

    allowed_config_fields = [
        "source_fields",
        "target_field",
        "seperator",
        "overwrite_target",
        "delete_source_fields",
    ]

    def __init__(self, filter_rule: FilterExpression, rule_config: dict):
        """
        Instantiate ConcatenatorRule based on a given filter and processor configuration.

        Parameters
        ----------
        filter_rule : FilterExpression
            Given lucene filter expression as a representation of the rule's logic.
        rule_config: dict
            Configuration fields from a given pipeline that refer to the processor instance.
        """
        super().__init__(filter_rule)
        self._config = rule_config
        self._source_fields = self._config.get("source_fields")
        self._target_field = self._config.get("target_field")
        self._seperator = self._config.get("seperator")
        self._overwrite_target = self._config.get("overwrite_target")
        self._delete_source_fields = self._config.get("delete_source_fields")

    def __eq__(self, other: "ConcatenatorRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                self._source_fields == other.source_fields,
                self._target_field == other.target_field,
                self._seperator == other.seperator,
                self._overwrite_target == other.overwrite_target,
                self._delete_source_fields == other.delete_source_fields,
            ]
        )

    @property
    def source_fields(self) -> str:  # pylint: disable=missing-docstring
        return self._source_fields

    @property
    def target_field(self) -> str:  # pylint: disable=missing-docstring
        return self._target_field

    @property
    def seperator(self) -> str:  # pylint: disable=missing-docstring
        return self._seperator

    @property
    def overwrite_target(self) -> bool:  # pylint: disable=missing-docstring
        return self._overwrite_target

    @property
    def delete_source_fields(self) -> bool:  # pylint: disable=missing-docstring
        return self._delete_source_fields

    @staticmethod
    def _create_from_dict(rule: dict) -> "ConcatenatorRule":
        ConcatenatorRule._check_rule_validity(rule, "concatenator")
        ConcatenatorRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return ConcatenatorRule(filter_expression, rule["concatenator"])

    @staticmethod
    def _check_if_valid(rule: dict):
        """
        Check validity of a given rule file in relation to the processor configuration
        in the given pipeline.

        Parameters
        ----------
        rule : dict
            Current rule to be checked for configuration or field reference problems.
        """
        concatenator_rule_config_fields = set(rule.get("concatenator", {}).keys())
        expected_config_fields = set(ConcatenatorRule.allowed_config_fields)

        unknown_fields = concatenator_rule_config_fields.difference(expected_config_fields)

        if unknown_fields:
            raise InvalidConcatenatorRuleDefinition(
                f"Unknown fields were given: '{', '.join(unknown_fields)}'"
            )

        for key in concatenator_rule_config_fields:
            config_value = rule.get("concatenator", {}).get(key)
            if key in ["overwrite_target", "delete_source_fields"]:
                if not isinstance(config_value, bool):
                    raise InvalidConcatenatorRuleDefinition(
                        f"The field '{key}' should be of type 'bool', but is '{type(config_value)}'"
                    )
            elif key in ["source_fields"]:
                if not isinstance(config_value, list):
                    raise InvalidConcatenatorRuleDefinition(
                        f"The field '{key}' should be of type 'list', but is '{type(config_value)}'"
                    )
                if not all(isinstance(element, str) for element in config_value):
                    raise InvalidConcatenatorRuleDefinition(
                        "The given field 'source_fields' should be a list of string values, but "
                        "the list also contains non 'str' values"
                    )
                if len(config_value) < 2:
                    raise InvalidConcatenatorRuleDefinition(
                        "At least two source fields should be given for the concatenation."
                    )
            else:
                if not isinstance(config_value, str):
                    raise InvalidConcatenatorRuleDefinition(
                        f"The field '{key}' should be of type 'str', but is '{type(config_value)}'"
                    )
