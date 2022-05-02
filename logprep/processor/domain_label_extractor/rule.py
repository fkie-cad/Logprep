"""
This module is used to split domains in a given field into it's corresponding labels/parts.
"""

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class DomainLabelExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for DomainLabelExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"DomainLabelExtractor rule ({message})")


class InvalidDomainLabelExtractorDefinition(DomainLabelExtractorRuleError):
    """Raise if DomainLabelExtractor definition invalid."""

    def __init__(self, definition):
        message = f"The following DomainLabelExtractor definition is invalid: {definition}"
        super().__init__(message)


class DomainLabelExtractorRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, domain_label_extractor_cfg: dict):
        """
        Instantiate DomainLabelExtractorRule based on a given filter and processor configuration.

        Parameters
        ----------
        filter_rule : FilterExpression
            Given lucene filter expression as a representation of the rule's logic.
        domain_label_extractor_cfg: dict
            Configuration fields from a given pipeline that refer to the processor instance.
        """
        super().__init__(filter_rule)

        self._target_field = domain_label_extractor_cfg["target_field"]
        self._output_field = domain_label_extractor_cfg["output_field"]

    def __eq__(self, other: "DomainLabelExtractorRule") -> bool:
        return all(
            [
                self._output_field == other.output_field,
                other.filter == self._filter,
                self._target_field == other.target_field,
            ]
        )

    @property
    def target_field(self) -> str:
        return self._target_field

    @property
    def output_field(self) -> str:
        return self._output_field

    @staticmethod
    def _create_from_dict(rule: dict) -> "DomainLabelExtractorRule":
        DomainLabelExtractorRule._check_rule_validity(rule, "domain_label_extractor")
        DomainLabelExtractorRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return DomainLabelExtractorRule(filter_expression, rule["domain_label_extractor"])

    @staticmethod
    def _check_if_valid(rule: dict):
        """
        Check validity of a given rule file in relation to the processor configuration in the given pipeline.

        Parameters
        ----------
        rule : dict
            Current rule to be checked for configuration or field reference problems.
        """

        domain_label_extractor_cfg = rule["domain_label_extractor"]

        if "target_field" not in domain_label_extractor_cfg.keys():
            raise InvalidDomainLabelExtractorDefinition(
                f"Missing 'target_field' in rule configuration."
            )
        elif not isinstance(domain_label_extractor_cfg["target_field"], str):
            raise InvalidDomainLabelExtractorDefinition(
                f"'target_field' should be 'str' and not"
                f" '{type(domain_label_extractor_cfg['target_field'])}'"
            )

        if "output_field" not in domain_label_extractor_cfg.keys():
            raise InvalidDomainLabelExtractorDefinition(
                f"Missing 'output_field' in rule configuration."
            )
        elif not isinstance(domain_label_extractor_cfg["output_field"], str):
            raise InvalidDomainLabelExtractorDefinition(
                f"'output_field' should be 'str' and not"
                f" '{type(domain_label_extractor_cfg['output_field'])}'"
            )
