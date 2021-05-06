"""This modules contains a factory for pre-detector processors."""

from logging import Logger

from logprep.processor.processor_factory_error import UnknownProcessorTypeError, InvalidConfigurationError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.pre_detector.processor import PreDetector


class InvalidPreDetectorFactoryConfigurationError(InvalidConfigurationError):
    """Base class for PreDetectorFactory specific exceptions."""


class InvalidRuleConfigurationError(InvalidPreDetectorFactoryConfigurationError):
    """Raise if rule configuration is invalid."""


class PreDetectorFactory(BaseFactory):
    """Create pre-detectors."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger):
        """Create an pre-detector."""
        PreDetectorFactory._check_configuration(configuration)

        pre_detector = PreDetector(
            name,
            configuration['pre_detector_topic'],
            configuration['tree_config'],
            configuration.get('alert_ip_list'),
            logger)

        pre_detector.add_rules_from_directory(configuration['rules'])

        return pre_detector

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError('\'type\' parameter required in pre_detector processor')
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'pre_detector'):
            raise UnknownProcessorTypeError

        for item in ('rules', 'pre_detector_topic'):
            if item not in configuration:
                raise InvalidConfigurationError(
                    f'Item "{item}" is missing in PreDetector configuration')

        if 'tree_config' not in configuration:
            raise InvalidConfigurationError('\'tree_config\' parameter required in pre_detector processor')
