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
from logprep.util.helper import add_field_to, get_dotted_field_value, add_and_overwrite


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
        self._add_label_fields(event, rule)
        self._add_label_values(event, rule)
        self._convert_label_categories_to_sorted_list(event)

    @staticmethod
    def _add_label_fields(event: dict, rule: LabelerRule):
        """Prepares the event by adding empty label fields"""
        add_field_to(event, "label", {})
        for key in rule.label:
            add_field_to(event, f"label.{key}", set())

    @staticmethod
    def _add_label_values(event: dict, rule: LabelerRule):
        """Adds the labels from the rule to the event"""
        for key in rule.label:
            label_key = f"label.{key}"
            label = get_dotted_field_value(event, label_key)
            if not isinstance(label, set):
                label = set(label)
                add_and_overwrite(event, label_key, label)
            label.update(rule.label[key])

    @staticmethod
    def _convert_label_categories_to_sorted_list(event: dict):
        label = get_dotted_field_value(event, "label")
        if label is None:
            return
        for category in label:
            category_key = f"label.{category}"
            category_value = get_dotted_field_value(event, category_key)
            sorted_category = sorted(list(category_value))
            add_and_overwrite(event, category_key, sorted_category)
