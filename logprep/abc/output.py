"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

from abc import abstractmethod
from copy import deepcopy
from typing import Any, Optional

from attrs import define, field, validators

from logprep.abc.connector import Connector
from logprep.abc.exceptions import LogprepException


class OutputError(LogprepException):
    """Base class for Output related exceptions."""

    def __init__(self, output: "Output", message: str) -> None:
        output.metrics.number_of_errors += 1
        super().__init__(f"{self.__class__.__name__} in {output.describe()}: {message}")


class OutputWarning(LogprepException):
    """Base class for Output related warnings."""

    def __init__(self, output: "Output", message: str) -> None:
        output.metrics.number_of_warnings += 1
        super().__init__(f"{self.__class__.__name__} in {output.describe()}: {message}")


class CriticalOutputError(OutputError):
    """A significant error occurred - log and don't process the event."""

    __match_args__ = ("raw_input",)

    def __init__(self, output: "Output", message: str, raw_input: Any) -> None:
        super().__init__(output, f"{message} -> event was written to error output if configured")
        self.raw_input = deepcopy(raw_input)
        self.message = message


class FatalOutputError(OutputError):
    """Must not be caught."""


class Output(Connector):
    """Connect to a output destination."""

    @define(kw_only=True)
    class Config(Connector.Config):
        """output config parameters"""

        default: bool = field(validator=validators.instance_of(bool), default=True)
        """ (Optional) if :code:`false` the event are not delivered to this output.
        But this output can be called as output for extra_data.
        """

    @property
    def default(self):
        """returns the default parameter"""
        return self._config.default

    @property
    def metric_labels(self) -> dict:
        """Return the metric labels for this component."""
        return {
            "component": "output",
            "description": self.describe(),
            "type": self._config.type,
            "name": self.name,
        }

    def __init__(self, name: str, configuration: "Connector.Config"):
        super().__init__(name, configuration)
        self.input_connector = None

    @abstractmethod
    def store(self, document: dict) -> Optional[bool]:
        """Store the document in the output destination.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.
        """

    @abstractmethod
    def store_custom(self, document: dict, target: str):
        """Store additional data in a custom location inside the output destination."""

    def _write_backlog(self):
        """Write the backlog to the output destination."""
