"""This rule enables to check if incoming documents are of a specific type
suitable for classification by amides.


The following example shows a complete rule:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: "sample_cmdline"'
    amides:
        source_fields: ["process.command_line"]
        target_field: "rule_attributions"
    description: Sample rule for AMIDES processor.

"""
from ruamel.yaml import YAML

from attrs import define, field, validators
from logprep.processor.field_manager.rule import FieldManagerRule

yaml = YAML(typ="safe", pure=True)


class AmidesRule(FieldManagerRule):
    """AmidesRule checks if incoming documents match given filter-expression
    of the Amides-processor.
    """

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config of AmidesRule to specify target field of the detection results."""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                validators.min_len(1),
                validators.max_len(1),
            ]
        )
        target_field: str = field(
            validator=validators.instance_of(str), default="rule_attributions"
        )
