"""This module contains a factory for DomainLabelExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.domain_label_extractor.processor import DomainLabelExtractor


class DomainLabelExtractorFactory(BaseFactory):
    """Factory used to instantiate DomainLabelExtractor processors."""

    mandatory_fields = ["generic_rules", "specific_rules", "tree_config"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DomainLabelExtractor:
        """
        Create a DomainLabelExtractor processor based on the processor configuration
        in the pipeline configuration.
        """
        DomainLabelExtractorFactory._check_configuration(configuration)

        return DomainLabelExtractor(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        DomainLabelExtractorFactory._check_common_configuration(
            processor_type="domain_label_extractor",
            existing_items=DomainLabelExtractorFactory.mandatory_fields,
            configuration=configuration,
        )
