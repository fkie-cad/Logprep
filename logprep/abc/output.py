"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

from abc import abstractmethod
from logging import Logger
from typing import Optional

from .connector import Connector


class OutputError(BaseException):
    """Base class for Output related exceptions."""


class CriticalOutputError(OutputError):
    """A significant error occurred - log and don't process the event."""

    def __init__(self, message, raw_input):
        self.raw_input = raw_input
        super().__init__(message)


class FatalOutputError(OutputError):
    """Must not be catched."""


class WarningOutputError(OutputError):
    """May be catched but must be displayed to the user/logged."""


class Output(Connector):
    """Connect to a output destination."""

    __slots__ = {"input_connector"}

    input_connector: Connector

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger):
        super().__init__(name, configuration, logger)
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

    @abstractmethod
    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Store an event when an error occurred during the processing."""
