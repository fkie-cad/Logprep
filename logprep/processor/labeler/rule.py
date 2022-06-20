"""This module is used to apply configured labeling rules on given documents."""

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule
from logprep.processor.labeler.labeling_schema import LabelingSchema


class LabelingRule(Rule):
    """Check if documents match a filter and add labels them."""

    def __init__(self, filter_rule: FilterExpression, label: dict):
        super().__init__(filter_rule)
        self._label = label

    def __eq__(self, other: "LabelingRule"):
        return (self._filter == other.filter) and (self._label == other.label)

    # pylint: disable=C0111
    @property
    def label(self) -> dict:
        return self._label

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "LabelingRule":
        LabelingRule._check_rule_validity(rule, "label")

        filter_expression = Rule._create_filter_expression(rule)
        return LabelingRule(filter_expression, rule["label"])

    def conforms_to_schema(self, schema: LabelingSchema) -> bool:
        """Check if labels are valid."""
        return schema.validate_labels(self._label)

    def add_parent_labels_from_schema(self, schema: LabelingSchema):
        """Add parent labels to this rule according to a given schema."""
        expanded_label = {}

        for category in self._label:
            expanded_label[category] = set()
            for label in self._label[category]:
                expanded_label[category].add(label)
                for parent in schema.get_parent_labels(category, label):
                    expanded_label[category].add(parent)
            self._label[category] = expanded_label[category]
