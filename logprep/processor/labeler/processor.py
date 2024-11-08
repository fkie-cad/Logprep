"""
Labeler
=======

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^

..  code-block:: yaml
    :linenos:

    - labelername:
        type: labeler
        schema: tests/testdata/labeler_rules/labeling/schema.json
        include_parent_labels: true
        generic_rules:
            - tests/testdata/labeler_rules/rules/
        specific_rules:
            - tests/testdata/labeler_rules/rules/

.. autoclass:: logprep.processor.labeler.processor.Labeler.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.labeler.rule
"""

from typing import Optional

from attr import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule
from logprep.util.helper import (
    get_dotted_field_value,
    add_batch_to_silent_fail,
)


class Labeler(Processor):
    """Processor used to label log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Labeler Configurations"""

        schema: str = field(validator=[validators.instance_of(str)])
        """Path to a labeling schema file. For string format see :ref:`getters`."""
        include_parent_labels: Optional[bool] = field(
            default=False, validator=validators.optional(validator=validators.instance_of(bool))
        )
        """If the option is deactivated only labels defined in a rule will be activated.
        Otherwise, also allowed labels in the path to the *root* of the corresponding category
        of a label will be added.
        This allows to search for higher level labels if this option was activated in the rule.
        """

    __slots__ = ["_schema", "_include_parent_labels"]

    _schema: LabelingSchema

    rule_class = LabelerRule

    def __init__(self, name: str, configuration: Processor.Config):
        self._schema = LabelingSchema.create_from_file(configuration.schema)
        super().__init__(name, configuration=configuration)

    def setup(self):
        super().setup()
        for rule in self._generic_rules + self._specific_rules:
            if self._config.include_parent_labels:
                rule.add_parent_labels_from_schema(self._schema)
            rule.conforms_to_schema(self._schema)

    def _apply_rules(self, event, rule):
        """Applies the rule to the current event"""
        targets = [f"label.{key}" for key in rule.label.keys()]
        contents = rule.label.values()
        add_batch_to_silent_fail(event, targets, contents)
        # convert sets into sorted lists
        contents = [sorted(list(get_dotted_field_value(event, target))) for target in targets]
        add_batch_to_silent_fail(event, targets, contents, overwrite_output_field=True)
