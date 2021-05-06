"""This module is used to create the configuration for the runner."""

from logging import Logger

from yaml import safe_load

from logprep.connector.connector_factory import ConnectorFactory
from logprep.connector.connector_factory_error import ConnectorFactoryError
from logprep.processor.processor_factory import ProcessorFactory
from logprep.processor.processor_factory_error import (UnknownProcessorTypeError,
                                                       InvalidConfigurationError as FactoryInvalidConfigurationError)


class InvalidConfigurationError(BaseException):
    """Base class for Configuration related exceptions."""

    def __init__(self, unprefixed_message: str = None, message: str = None):
        if unprefixed_message is not None:
            super().__init__(unprefixed_message)
        elif message is not None:
            super().__init__(f'Invalid Configuration: {message}')
        else:
            super().__init__('Invalid Configuration.')


class RequiredConfigurationKeyMissingError(InvalidConfigurationError):
    """Raise if required option is missing in configuration."""

    def __init__(self, key: str):
        super().__init__(f'Required option is missing: {key}')


class InvalidLabelingSchemaError(InvalidConfigurationError):
    """Raise if labeling schema is invalid."""

    def __init__(self, message: str):
        super().__init__(f'Invalid labeling schema: {message}')


class InvalidRulesError(InvalidConfigurationError):
    """Raise if set of rules is invalid."""

    def __init__(self, message: str):
        super().__init__(f'Invalid rule set: {message}')


class InvalidProcessorConfigurationError(InvalidConfigurationError):
    """Raise if processor configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f'Invalid processor config: {message}')


class InvalidConnectorConfigurationError(InvalidConfigurationError):
    """Raise if connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f'Invalid connector configuration: {message}')


class Configuration(dict):
    """Used to create and verify a configuration dict parsed from a YAML file."""

    @staticmethod
    def create_from_yaml(path: str) -> 'Configuration':
        """Create configuration from a YAML file.

        Parameters
        ----------
        path : str
            Path of file to create configuration from.

        Returns
        -------
        config : Configuration
            Configuration object based on dictionary.

        """
        with open(path, 'r') as file:
            yaml_configuration = safe_load(file)
        config = Configuration()
        config.update(yaml_configuration)

        return config

    def verify(self, logger: Logger):
        """Verify the configuration."""
        self._verify_required_keys_exist()
        self._verify_values_make_sense()
        self._verify_connector()
        self._verify_pipeline(logger)

    def _verify_required_keys_exist(self):
        required_keys = ['process_count', 'connector', 'timeout', 'pipeline']

        for key in required_keys:
            if key not in self:
                raise RequiredConfigurationKeyMissingError(key)

    def _verify_values_make_sense(self):
        if self['process_count'] < 1:
            raise InvalidConfigurationError(
                message='Process count must be an integer of one or larger, not: {}'.format(self['process_count']))
        if not self['pipeline']:
            raise InvalidConfigurationError(message='"pipeline" must contain at least one item!')

    def _verify_connector(self):
        try:
            _, _ = ConnectorFactory.create(self['connector'])
        except ConnectorFactoryError as error:
            raise InvalidConnectorConfigurationError(str(error))
        except KeyError:
            raise RequiredConfigurationKeyMissingError('connector')

    def _verify_pipeline(self, logger: Logger):
        try:
            for processor_config in self['pipeline']:
                ProcessorFactory.create(processor_config, logger)
        except (FactoryInvalidConfigurationError, UnknownProcessorTypeError) as error:
            raise InvalidProcessorConfigurationError(str(error))
