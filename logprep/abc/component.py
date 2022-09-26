""" abstract module for connectors"""
import sys
from abc import ABC
from logging import Logger

from attr import define, field, validators
from logprep.util.helper import camel_to_snake


class Component(ABC):
    """Abstract Component Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config:
        """Common Configurations"""

        type: str = field(validator=validators.instance_of(str))
        """Type of the component"""

    __slots__ = ["name", "_logger", "_config"]

    if not sys.version_info.minor < 7:
        __slots__.append("__dict__")

    name: str
    _logger: Logger
    _config: Config

    def __init__(self, name: str, configuration: "Component.Config", logger: Logger):
        self._logger = logger
        self._config = configuration
        self.name = name

    def __repr__(self):
        return camel_to_snake(self.__class__.__name__)

    def describe(self) -> str:
        """Provide a brief name-like description of the connector.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> ConfluentKafkaInput(name)

        """
        return f"{self.__class__.__name__} ({self.name})"

    def setup(self):
        """Set the component up.

        This is optional.

        """

    def shut_down(self):
        """Stop processing of this component.

        Optional: Called when stopping the pipeline

        """
