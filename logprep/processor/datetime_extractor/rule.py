"""This module is used to extract date times and split them into multiple fields."""

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class DateTimeExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for DateTimeExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"DateTimeExtractor rule ({message}): ")


class InvalidDateTimeExtractorDefinition(DateTimeExtractorRuleError):
    """Raise if DateTimeExtractor definition invalid."""

    def __init__(self, definition):
        message = f"The following DateTimeExtractor definition is invalid: {definition}"
        super().__init__(message)


class DateTimeExtractorRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, datetime_extractor_cfg: dict):
        super().__init__(filter_rule)

        self._datetime_field = datetime_extractor_cfg["datetime_field"]
        self._destination_field = datetime_extractor_cfg.get("destination_field", {})

    def __eq__(self, other: "DateTimeExtractorRule") -> bool:
        return (
            (other.filter == self._filter)
            and (self._datetime_field == other.datetime_field)
            and (self._destination_field == other.destination_field)
        )

    def __hash__(self) -> int:
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def datetime_field(self) -> str:
        return self._datetime_field

    @property
    def destination_field(self) -> str:
        return self._destination_field

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "DateTimeExtractorRule":
        DateTimeExtractorRule._check_rule_validity(rule, "datetime_extractor")
        DateTimeExtractorRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return DateTimeExtractorRule(filter_expression, rule["datetime_extractor"])

    @staticmethod
    def _check_if_valid(rule: dict):
        datetime_extractor_cfg = rule["datetime_extractor"]
        for field in ("datetime_field", "destination_field"):
            if not isinstance(datetime_extractor_cfg[field], str):
                raise InvalidDateTimeExtractorDefinition(
                    '"{}" value "{}" is not a string!'.format(field, datetime_extractor_cfg[field])
                )
