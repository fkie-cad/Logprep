"""This module is used to replace a text field using a template."""

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class TemplateReplacerRuleError(InvalidRuleDefinitionError):
    """Base class for TemplateReplacer rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"TemplateReplacer rule ({message}): ")


class InvalidTemplateReplacerDefinition(TemplateReplacerRuleError):
    """Raise if TemplateReplacer definition invalid."""

    def __init__(self, definition):
        message = f"The following TemplateReplacer definition is invalid: {definition}"
        super().__init__(message)


class TemplateReplacerRule(Rule):
    """Check if documents match a filter."""

    def __eq__(self, other: "TemplateReplacerRule") -> bool:
        return other.filter == self._filter

    @staticmethod
    def _create_from_dict(rule: dict) -> "TemplateReplacerRule":
        TemplateReplacerRule._check_rule_validity(rule, "template_replacer")

        filter_expression = Rule._create_filter_expression(rule)
        return TemplateReplacerRule(filter_expression)
