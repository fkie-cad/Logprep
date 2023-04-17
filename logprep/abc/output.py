"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

from abc import abstractmethod
from logging import Logger
from typing import Optional

from attrs import define, field, validators

from logprep.abc.connector import Connector
from logprep.abc.input import Input


class OutputError(BaseException):
    """Base class for Output related exceptions."""

    def __init__(self, output: "Output", message: str) -> None:
        super().__init__(f"{self.__class__.__name__} in {output.describe()}: {message}")


class CriticalOutputError(OutputError):
    """A significant error occurred - log and don't process the event."""

    def __init__(self, output, message, raw_input):
        if raw_input:
            output.store_failed(str(self), raw_input, {})
        output.metrics.number_of_errors += 1
        super().__init__(output, f"{message} for event: {raw_input}")


class FatalOutputError(OutputError):
    """Must not be catched."""

    def __init__(self, output, message) -> None:
        output.metrics.number_of_errors += 1
        super().__init__(output, message)


class WarningOutputError(OutputError):
    """May be catched but must be displayed to the user/logged."""

    def __init__(self, output, message) -> None:
        output.metrics.number_of_warnings += 1
        super().__init__(output, message)


class Output(Connector):
    """Connect to a output destination."""

    @define(kw_only=True)
    class Config(Connector.Config):
        """output config parameters"""

        default: bool = field(validator=validators.instance_of(bool), default=True)
        """ (Optional) if :code:`false` the event are not delivered to this output.
        But this output can be called as output for extra_data.
        """

    __slots__ = {"input_connector"}

    input_connector: Optional[Input]

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self.input_connector = None

    @property
    def default(self):
        """returns the default parameter"""
        return self._config.default

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

    @abstractmethod
    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Store an event when an error occurred during the processing."""
