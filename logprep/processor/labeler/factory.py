"""This module contains a factory for labeler processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.labeler.exceptions import InvalidIncludeParentsValueError
from logprep.processor.labeler.processor import Labeler
from logprep.processor.labeler.rule import LabelingRule


class LabelerFactory(BaseFactory):
    """Create labelers."""

    processor_type = Labeler
    rule_type = LabelingRule

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Labeler:
        """Create a labeler."""
        LabelerFactory._add_defaults_to_configuration(configuration)
        LabelerFactory._check_configuration(configuration)

        labeler = Labeler(
            name=name,
            specific_rules_dirs=configuration.get("specific_rules"),
            generic_rules_dirs=configuration.get("generic_rules"),
            labeling_schema=configuration.get("schema"),
            include_parent_labels=configuration["include_parent_labels"],
            tree_config=configuration.get("tree_config"),
            logger=logger,
        )
        
        return labeler

    @staticmethod
    def _add_defaults_to_configuration(configuration: dict):
        if "include_parent_labels" not in configuration:
            configuration["include_parent_labels"] = False  # default

    @staticmethod
    def _check_configuration(configuration: dict):
        LabelerFactory._check_common_configuration(
            processor_type="labeler",
            existing_items=["schema", "include_parent_labels"],
            configuration=configuration,
        )

        if "include_parent_labels" in configuration and not isinstance(
            configuration["include_parent_labels"], bool
        ):
            raise InvalidIncludeParentsValueError()
