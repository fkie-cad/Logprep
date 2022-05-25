"""module for processor configuration """
import importlib
import os
from typing import TYPE_CHECKING, Any, Mapping

from logprep import processor
from logprep.util.helper import snake_to_camel

if TYPE_CHECKING:
    from logprep.abc import Processor


class ProcessorConfigurationError(ValueError):
    """is raised on invalid processor config"""


class ProcessorConfiguration:
    """factory and adapter for generating config"""

    @classmethod
    def create(cls, config_: Mapping[str, Any]) -> "Processor.Config":
        """factory method to create processor configuration

        Parameters
        ----------
        config_ : Mapping[str, Any]
            the config dict

        Returns
        -------
        Processor.Config
            the processor configuration

        Raises
        ------
        ProcessorConfigurationError
            raised if type not in config or processor not found
        """
        if "type" not in config_:
            raise ProcessorConfigurationError("'type' not found in configuration")
        item_filter = lambda file_item: not any([file_item.startswith("_"), file_item == "base"])
        processors = list(filter(item_filter, os.listdir(processor.__path__[0])))
        processor_type = config_.get("type")
        if processor_type not in processors:
            raise ProcessorConfigurationError(f"processor '{processor_type}' does not exist")
        processor_module = importlib.import_module(f"logprep.processor.{processor_type}.processor")
        processor_class_name = snake_to_camel(processor_type)
        processor_class = getattr(processor_module, processor_class_name)
        return processor_class.Config(**config_)
