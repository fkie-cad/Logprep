"""This module contains a factory to create processors."""

from typing import Tuple
from os.path import dirname, join, isdir
from os import listdir
from logging import getLogger, Logger, DEBUG
from copy import deepcopy

import pkgutil

from logprep.processor.processor_factory_error import (
    UnknownProcessorTypeError,
    NotExactlyOneEntryInConfigurationError,
    NoTypeSpecifiedError,
    InvalidConfigSpecificationError,
)
from logprep.processor.base.factory import BaseFactory
from logprep.processor.base.processor import BaseProcessor


class ProcessorFactory:
    """Create processors."""

    disabled_logger = getLogger("DISABLED")
    disabled_logger.disabled = True

    processors_factory_map = dict()
    already_added_classes = []

    @classmethod
    def load_plugins(cls, plugin_dir: str):
        """Discover and load processor plugins."""
        directories = []
        for item in listdir(plugin_dir):
            if isdir(join(plugin_dir, item)) and "factory.py" in listdir(join(plugin_dir, item)):
                directories.append(item)

        for directory in directories:
            if directory != "base":
                cls.processors_factory_map[directory] = dict()
                for (importer, name, _) in pkgutil.iter_modules([join(plugin_dir, directory)]):
                    if name == "factory":
                        pre_loading_submodules = deepcopy(BaseFactory.__subclasses__())
                        module = importer.find_module(name)
                        module.load_module(name)
                        unique_subclasses = []
                        new_subclasses = []
                        for item in BaseFactory.__subclasses__():
                            if item not in pre_loading_submodules:
                                new_subclasses.append(item)
                        for subclass in new_subclasses:
                            if subclass.__name__ not in (usc.__name__ for usc in unique_subclasses):
                                unique_subclasses.append(subclass)

                        new_classes = []
                        for unique_subclass in unique_subclasses:
                            if unique_subclass.__name__ not in (
                                item.__name__ for item in cls.already_added_classes
                            ):
                                new_classes.append(unique_subclass)

                        if len(new_classes) == 1:
                            cls.processors_factory_map[directory] = new_classes[0]
                            cls.already_added_classes.append(new_classes[0])
                if not cls.processors_factory_map[directory]:
                    raise BaseException(f"There exist multiple plugins of the type: {directory}")

    @classmethod
    def create(cls, configuration: dict, logger: Logger) -> BaseProcessor:
        """Create processor."""
        ProcessorFactory._fail_is_not_a_valid_config_specification(configuration)
        name, section, processor_type = ProcessorFactory._get_name_section_and_type(configuration)

        logging_enabled = configuration[name].get("logging", True)
        if not logging_enabled:
            logger = cls.disabled_logger

        processor_factory = cls.processors_factory_map.get(processor_type)
        if processor_factory:
            processor = processor_factory.create(name, section, logger)
            return processor

        if logger.isEnabledFor(DEBUG):
            logger.debug(f"Failed to create unknown processor type: '{processor_type}'")
        raise UnknownProcessorTypeError(processor_type)

    @staticmethod
    def _fail_is_not_a_valid_config_specification(configuration: dict):
        if len(configuration) != 1:
            raise NotExactlyOneEntryInConfigurationError

        _, config_section = ProcessorFactory._get_name_and_section(configuration)

        if not isinstance(config_section, dict):
            raise InvalidConfigSpecificationError

        if "type" not in config_section:
            raise NoTypeSpecifiedError()

    @staticmethod
    def _get_name_and_section(configuration: dict) -> Tuple[str, dict]:
        name = list(configuration.keys())[0]
        config_section = configuration[name]

        return name, config_section

    @staticmethod
    def _get_name_section_and_type(configuration: dict) -> Tuple[str, dict, str]:
        name, config_section = ProcessorFactory._get_name_and_section(configuration)

        return name, config_section, config_section["type"].lower()


pkg_dir = dirname(__file__)
ProcessorFactory.load_plugins(pkg_dir)
