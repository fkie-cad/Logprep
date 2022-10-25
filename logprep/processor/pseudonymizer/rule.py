"""This module is used to get documents that match a pseudonymization filter."""

from typing import List
from attrs import define, field, validators

from logprep.util.helper import pop_dotted_field_value, add_and_overwrite
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


class PseudonymizeRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Pseudonymizer"""

        pseudonyms: dict = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of(str),
            )
        )
        url_fields: list = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str)),
            factory=list,
        )

    @classmethod
    def normalize_rule_dict(cls, rule):
        if rule.get("pseudonymizer", {}).get("pseudonyms") is None:
            pseudonyms = pop_dotted_field_value(rule, "pseudonymize")
        if pseudonyms is not None:
            add_and_overwrite(rule, "pseudonymize.pseudonyms", pseudonyms)
        if rule.get("pseudonymizer", {}).get("url_fields") is None:
            url_fields = pop_dotted_field_value(rule, "url_fields")
        if url_fields is not None:
            add_and_overwrite(rule, "pseudonymize.url_fields", url_fields)

    # pylint: disable=C0111
    @property
    def pseudonyms(self) -> dict:
        return self._config.pseudonyms

    @property
    def url_fields(self) -> List[str]:
        return self._config.url_fields

    # pylint: enable=C0111
