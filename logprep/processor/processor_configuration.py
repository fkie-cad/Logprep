from typing import Any, Mapping
from config import Configuration, InterpolateEnumType, InterpolateType


class ProcessorConfigurationError(ValueError):
    """is raised on invalid processor config"""


class ProcessorConfiguration(Configuration):
    """class for generating config"""

    def __init__(
        self,
        config_: Mapping[str, Any],
        lowercase_keys: bool = False,
        interpolate: InterpolateType = False,
        interpolate_type: InterpolateEnumType = ...,
    ):
        self.is_valid(config_)
        super().__init__(config_, lowercase_keys, interpolate, interpolate_type)

    def is_valid(self, config):
        """validates config mapping"""
        if "type" not in config:
            raise ProcessorConfigurationError("config is not valid")

    def reload(self) -> None:
        pass
