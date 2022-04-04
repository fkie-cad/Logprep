"""This module contains a factory for DomainLabelExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.domain_label_extractor.processor import DomainLabelExtractor


class DomainLabelExtractorFactory(BaseFactory):
    """Factory used to instantiate DomainLabelExtractor processors."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DomainLabelExtractor:
        """
        Create a DomainLabelExtractor processor based on the processor configuration
        in the pipeline configuration.
        """
        DomainLabelExtractorFactory._check_configuration(configuration)

        domain_label_extractor = DomainLabelExtractor(
            name,
            configuration.get("tree_config"),
            configuration.get("tld_lists", None),
            configuration.get("tagging_field_name", "tags"),
            logger,
        )
        domain_label_extractor.add_rules_from_directory(configuration["rules"])

        return domain_label_extractor

    @staticmethod
    def _check_configuration(configuration: dict):
        DomainLabelExtractorFactory._check_common_configuration(
            "domain_label_extractor", ["rules"], configuration
        )
