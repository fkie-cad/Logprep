"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

This rule enables to check if incoming documents are of a specific type
suitable for classification by the :code:`Amides` processor. The specified
:code:`source_field` should contain command line strings. In case of an
positive detection result, rule attributions are written into
the :code:`target_field`.

The following example shows a complete rule:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: "sample_cmdline"'
    amides:
        source_fields: ["process.command_line"]
        target_field: "rule_attributions"
    description: Sample rule for AMIDES processor.

.. autoclass:: logprep.processor.amides.rule.AmidesRule.Config
   :noindex:
   :members:
   :inherited-members:
   :no-undoc-members:
"""

from attrs import define, field, validators
from ruamel.yaml import YAML

from logprep.processor.field_manager.rule import FieldManagerRule

yaml = YAML(typ="safe", pure=True)


class AmidesRule(FieldManagerRule):
    """AmidesRule checks if incoming documents contain fields suitable
    for classification by the Amides processor.
    """

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config of AmidesRule to specify source fields of command lines and
        target field of rule attribution results."""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                validators.min_len(1),
                validators.max_len(1),
            ]
        )
        target_field: str = field(validator=validators.instance_of(str), default="amides")
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(
            init=False, repr=False, eq=False, default=False, validator=validators.instance_of(bool)
        )
