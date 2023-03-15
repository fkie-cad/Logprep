"""This rule enables to check if incoming documents are of a specific type
suitable for classification by amides.


The following example shows a complete rule:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: "very malicious!"'
    amides:
      
    description: Some malicious event.

"""
from ruamel.yaml import YAML

from attrs import define, field, validators

from logprep.processor.base.rule import InvalidRuleDefinitionError, Rule

yaml = YAML(typ="safe", pure=True)


class AmidesRuleError(InvalidRuleDefinitionError):
    """Base-class for AmidesRule-related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"Amides rule ({message})")


class AmidesRule(Rule):
    """AmidesRule checks if incoming documents match given filter-expression
    of the Amides-processor.
    """

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config of AmidesRule to catchcommand-line field and
        rule attributions field from rule file."""

        commandline_field: str = field(validator=validators.instance_of(str))
        rule_attributions_field: str = field(validator=validators.instance_of(str))

    @property
    def cmdline_field(self):
        """Return name of the specified commandline-field which contains the commandline
        to analyze.
        """
        return self._config.commandline_field

    @property
    def rule_attributions_field(self):
        """Return name of the field which will hold results of the rule attribution
        (if any).
        """
        return self._config.rule_attributions_field

    def __eq__(self, other: "AmidesRule") -> bool:
        return all(
            [
                super().__eq__(other),
                self.cmdline_field == other.cmdline_field,
                self.rule_attributions_field == other.rule_attributions_field,
            ]
        )
