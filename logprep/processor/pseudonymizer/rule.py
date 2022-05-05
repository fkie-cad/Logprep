"""This module is used to get documents that match a pseudonymization filter."""

from typing import List
from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule


class PseudonymizerRuleError(BaseException):
    """Base class for Pseudonymizer rule related exceptions."""

    def __init__(self, message):
        super().__init__(f"Normalizer rule ({message}): ")


class InvalidPseudonymizationDefinition(PseudonymizerRuleError):
    """Raise if pseudonymization definition invalid."""

    def __init__(self, definition):
        message = f"The following pseudonymization definition is invalid: {definition}"
        super().__init__(message)


class PseudonymizerRule(Rule):
    """Check if documents match a filter."""

    def __init__(
        self, filter_rule: FilterExpression, pseudonyms: dict, url_fields: List[str] = None
    ):
        super().__init__(filter_rule)
        self._pseudonyms = pseudonyms
        self._url_fields = url_fields if url_fields else list()

    def __eq__(self, other: "PseudonymizerRule") -> bool:
        filter_equal = self._filter == other.filter
        pseudonyms_equal = self._pseudonyms == other.pseudonyms
        url_fields_equal = self._url_fields == other.url_fields
        return filter_equal and pseudonyms_equal and url_fields_equal

    # pylint: disable=C0111
    @property
    def pseudonyms(self) -> dict:
        return self._pseudonyms

    @property
    def url_fields(self) -> List[str]:
        return self._url_fields

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "PseudonymizerRule":
        PseudonymizerRule._check_rule_validity(rule, "pseudonymize", optional_keys={"url_fields"})
        if "url_fields" in rule:
            if not isinstance(rule.get("url_fields"), list):
                raise InvalidPseudonymizationDefinition(
                    "'{}: {}' value must be a list!".format("url_fields", rule["url_fields"])
                )

        filter_expression = Rule._create_filter_expression(rule)
        return PseudonymizerRule(filter_expression, rule["pseudonymize"], rule.get("url_fields"))
