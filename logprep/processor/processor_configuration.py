"""module for processor configuration """
import importlib
import os
from typing import TYPE_CHECKING, Any, Mapping

from logprep import processor
from logprep.processor.processor_factory_error import (
    NoTypeSpecifiedError,
    UnknownProcessorTypeError,
)
from logprep.util.helper import snake_to_camel

if TYPE_CHECKING:
    from logprep.abc import Processor


class ProcessorConfiguration:
    """factory and adapter for generating config"""

    @classmethod
    def create(cls, processor_name: str, config_: Mapping[str, Any]) -> "Processor.Config":
        """factory method to create processor configuration

        Parameters
        ----------
        processor_name: str
            the name of the processor
        config_ : Mapping[str, Any]
            the config dict

        Returns
        -------
        Processor.Config
            the processor configuration
        """
        processor_class = cls.get_processor_class(processor_name, config_)
        return processor_class.Config(**config_)

    @staticmethod
    def get_processor_class(processor_name: str, config_: Mapping[str, Any]):
        """gets the processorclass from config

        Parameters
        ----------
        processor_name : str
            The name of the processor
        config_ : Mapping[str, Any]
            the configuration with setted `type`

        Returns
        -------
        Processor
            The requested processor

        Raises
        ------
        UnknownProcessorTypeError
            if processor is not found
        NoTypeSpecifiedError
            if type is not found in config object
        """
        if "type" not in config_:
            raise NoTypeSpecifiedError(processor_name)
        item_filter = lambda file_item: not any([file_item.startswith("_"), file_item == "base"])
        processors = list(filter(item_filter, os.listdir(processor.__path__[0])))
        processor_type = config_.get("type")
        if processor_type not in processors:
            raise UnknownProcessorTypeError(processor_type)
        processor_module = importlib.import_module(f"logprep.processor.{processor_type}.processor")
        processor_class_name = snake_to_camel(processor_type)
        return getattr(processor_module, processor_class_name)
