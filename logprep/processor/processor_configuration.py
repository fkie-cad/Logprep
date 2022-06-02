"""module for processor configuration """
from typing import TYPE_CHECKING, Any, Mapping

from logprep.processor.processor_registry import ProcessorRegistry
from logprep.processor.processor_factory_error import (
    NoTypeSpecifiedError,
    UnknownProcessorTypeError,
)

if TYPE_CHECKING:  # pragma: no cover
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
        processors = ProcessorRegistry.mapping
        processor_type = config_.get("type")
        if processor_type not in processors:
            raise UnknownProcessorTypeError(processor_type)
        return ProcessorRegistry.get_processor_class(processor_type)
