"""This module contains a factory for pre-detector processors."""

from logging import Logger

from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.pre_detector.processor import PreDetector


class InvalidPreDetectorFactoryConfigurationError(InvalidConfigurationError):
    """Base class for PreDetectorFactory specific exceptions."""


class InvalidRuleConfigurationError(InvalidPreDetectorFactoryConfigurationError):
    """Raise if rule configuration is invalid."""


class PreDetectorFactory(BaseFactory):
    """Create pre-detectors."""

    mandatory_fields = ["specific_rules", "generic_rules", "pre_detector_topic"]

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger):
        """Create an pre-detector."""
        PreDetectorFactory._check_configuration(configuration)

        return PreDetector(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        PreDetectorFactory._check_common_configuration(
            "pre_detector", PreDetectorFactory.mandatory_fields, configuration
        )
