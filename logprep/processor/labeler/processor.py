"""This module contains functionality for labeling log events."""

from logging import Logger

from attr import define, field, validators

from logprep.abc import Processor
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelingRule


class Labeler(Processor):
    """Processor used to label log events."""

    @define
    class Config(Processor.Config):
        """labeler config"""

        schema: str = field(validator=validators.instance_of(str))

    __slots__ = ["_schema", "_include_parent_labels"]

    _include_parent_labels: bool

    _schema: LabelingSchema

    rule_class = LabelingRule

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        self._schema = LabelingSchema.create_from_file(configuration.get("schema"))
        self._include_parent_labels = configuration.get("include_parent_labels", False)
        super().__init__(name, configuration=configuration, logger=logger)
        for rule in self._generic_rules + self._specific_rules:
            if self._include_parent_labels:
                rule.add_parent_labels_from_schema(self._schema)
            rule.conforms_to_schema(self._schema)

    def _apply_rules(self, event, rule):
        """Applies the rule to the current event"""
        self._add_label_fields(event, rule)
        self._add_label_values(event, rule)
        self._convert_label_categories_to_sorted_list(event)

    @staticmethod
    def _add_label_fields(event: dict, rule: LabelingRule):
        """Prepares the event by adding empty label fields"""
        if "label" not in event:
            event["label"] = {}

        for key in rule.label:
            if key not in event["label"]:
                event["label"][key] = set()

    @staticmethod
    def _add_label_values(event: dict, rule: LabelingRule):
        """Adds the labels from the rule to the event"""
        for key in rule.label:
            if not isinstance(event["label"][key], set):
                event["label"][key] = set(event["label"][key])

            event["label"][key].update(rule.label[key])

    @staticmethod
    def _convert_label_categories_to_sorted_list(event: dict):
        if "label" in event:
            for category in event["label"]:
                event["label"][category] = sorted(list(event["label"][category]))
