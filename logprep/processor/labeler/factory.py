"""This module contains a factory for labeler processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.labeler.processor import Labeler
from logprep.processor.labeler.rule import LabelingRule
from logprep.processor.processor_factory_error import InvalidConfigurationError


class LabelerFactory(BaseFactory):
    """Create labelers."""

    processor_type = Labeler
    rule_type = LabelingRule

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Labeler:
        """Create a labeler."""
        LabelerFactory._check_configuration(configuration)

        labeler = Labeler(
            name=name,
            configuration=configuration,
            logger=logger,
        )

        return labeler

    @staticmethod
    def _check_configuration(configuration: dict):
        LabelerFactory._check_common_configuration(
            processor_type="labeler",
            existing_items=["schema"],
            configuration=configuration,
        )

        if "include_parent_labels" in configuration and not isinstance(
            configuration["include_parent_labels"], bool
        ):
            raise InvalidConfigurationError("'include_parent_labels' is not a boolean")
