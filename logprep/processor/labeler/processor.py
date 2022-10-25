"""
Labeler
-------
Labeling-Schema and validating Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The validation of schemata and rules can be started separately by executing:

..  code-block:: bash

    PYTHONPATH="." python3 logprep/util/schema_and_rule_checker.py $LABELING_SCHEMA $RULES

Where :code:`$LABELING_SCHEMA` is the path to a labeling schema file and :code:`$RULES` is the path
to a directory with rule files.

Example
^^^^^^^

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

"""

from logging import Logger
from typing import Optional

from attr import define, field, validators

from logprep.abc import Processor
from logprep.util.validators import file_validator, json_validator
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule


class Labeler(Processor):
    """Processor used to label log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Labeler Configurations"""

        schema: str = field(validator=[file_validator, json_validator])
        """Path to a labeling schema file"""
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

    def __init__(
        self,
        name: str,
        configuration: Processor.Config,
        logger: Logger,
    ):
        self._schema = LabelingSchema.create_from_file(configuration.schema)
        super().__init__(name, configuration=configuration, logger=logger)
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
        if "label" not in event:
            event["label"] = {}

        for key in rule.label:
            if key not in event["label"]:
                event["label"][key] = set()

    @staticmethod
    def _add_label_values(event: dict, rule: LabelerRule):
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
