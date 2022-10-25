"""This module is used to apply configured labeling rules on given documents."""
from attrs import define, field, validators

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError
from logprep.processor.labeler.labeling_schema import LabelingSchema


class LabelRule(Rule):
    """Check if documents match a filter and add labels them."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Concatenator"""

        label: dict = field(validator=validators.instance_of(dict))

    # pylint: disable=C0111
    @property
    def label(self) -> dict:
        return self._config.label

    # pylint: enable=C0111

    @classmethod
    def _create_from_dict(cls, rule: dict) -> "Rule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("label")
        if config is None:
            raise InvalidRuleDefinitionError("config not under key label")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = cls.Config(label=config)
        return cls(filter_expression, config)

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
