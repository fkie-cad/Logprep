"""This module contains functionality for creating processors of given type."""
from logging import Logger
from typing import List

from logprep.processor.processor_factory_error import (
    UnknownProcessorTypeError,
    InvalidConfigurationError,
)


class BaseFactory:
    """Create processors of given type."""

    processor_type = None
    rule_type = None

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger):
        raise NotImplementedError

    @staticmethod
    def _check_configuration(configuration: dict):
        raise NotImplementedError

    @staticmethod
    def _check_common_configuration(
        processor_type: str, existing_items: List[str], configuration: dict
    ):
        if "type" not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration["type"], str)) or (
            configuration["type"].lower() != processor_type
        ):
            raise UnknownProcessorTypeError

        for item in existing_items:
            if item not in configuration:
                raise InvalidConfigurationError(
                    f"Item {item} is missing in '{processor_type}' configuration"
                )
