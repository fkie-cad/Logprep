"""This module contains a factory for DomainLabelExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.domain_label_extractor.processor import DomainLabelExtractor
from logprep.processor.processor_factory_error import InvalidConfigurationError


class DomainLabelExtractorFactory(BaseFactory):
    """Factory used to instantiate DomainLabelExtractor processors."""

    mandatory_fields = ["type", "generic_rules", "specific_rules", "tree_config"]

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
            tld_lists=configuration.get("tld_lists", None),
            tagging_field_name=configuration.get("tagging_field_name", "tags"),
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        for field in DomainLabelExtractorFactory.mandatory_fields:
            if field not in configuration.keys():
                raise InvalidConfigurationError
