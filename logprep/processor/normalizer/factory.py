"""This module contains a factory for normalizer processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.normalizer.processor import Normalizer


class NormalizerFactory(BaseFactory):
    """Create normalizers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Normalizer:
        """Create a normalizer."""
        return Normalizer(name=name, configuration=configuration, logger=logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        NormalizerFactory._check_common_configuration(
            "normalizer", ["specific_rules", "generic_rules", "regex_mapping"], configuration
        )
        if "count_grok_pattern_matches" in configuration:
            required_items = ("count_directory_path", "write_period")
            for item in required_items:
                if item not in configuration["count_grok_pattern_matches"]:
                    raise InvalidConfigurationError(
                        f"Item 'count_grok_pattern_matches.{item}' is missing in "
                        f"'normalizer' configuration"
                    )
