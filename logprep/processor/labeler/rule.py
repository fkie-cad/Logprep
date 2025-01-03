"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The labeler requires the additional field :code:`label`.
The keys under :code:`label` define the categories under which a label should be added.
The values are a list of labels that should be added under a category.

In the following example, the label :code:`execute` will be added
to the labels of the category :code:`action`:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'command: "executing something"'
    labeler:
        label:
            action:
            - execute
    description: '...'

.. autoclass:: logprep.processor.labeler.rule.LabelerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from typing import Iterable

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.processor.labeler.labeling_schema import LabelingSchema


class LabelerRule(FieldManagerRule):
    """Check if documents match a filter and add labels them."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for Labeler"""

        label: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(Iterable),
                ),
            ]
        )
        """Mapping of a category and a list of labels to add"""

    # pylint: disable=C0111
    @property
    def label(self) -> dict:
        return self._config.label

    # pylint: enable=C0111

    @property
    def prefixed_label(self) -> dict:
        return {f"label.{key}": list(value) for key, value in self.label.items()}

    def conforms_to_schema(self, schema: LabelingSchema) -> bool:
        """Check if labels are valid."""
        return schema.validate_labels(self._config.label)

    def add_parent_labels_from_schema(self, schema: LabelingSchema):
        """Add parent labels to this rule according to a given schema."""
        expanded_label = {}

        for category in self._config.label:
            expanded_label[category] = set()
            for label in self._config.label[category]:
                expanded_label[category].add(label)
                for parent in schema.get_parent_labels(category, label):
                    expanded_label[category].add(parent)
            self._config.label[category] = expanded_label[category]
