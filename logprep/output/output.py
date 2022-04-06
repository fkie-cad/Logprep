"""This module provides the abstract base class for all output endpoints.

New output endpoint types are created by implementing it.

"""

from abc import ABCMeta, abstractmethod


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


class Output(metaclass=ABCMeta):
    """Connect to a source for log data."""

    def setup(self):
        """Set the output up, e.g. connect to a database.

        This is optional.

        """

    @abstractmethod
    def describe_endpoint(self) -> str:
        """Return a brief description of the endpoint for this output.

        This may be used as a word in a sentence.
        Setting a description is optional.

        """
        return "Output: the.host.name.tld:1234"

    @abstractmethod
    def store(self, document: dict):
        """Store the document.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.

        """

    @abstractmethod
    def store_custom(self, document: dict, target: str):
        """Store additional data in a custom location."""

    @abstractmethod
    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Store an event when an error occurred during the processing."""

    def shut_down(self):
        """Close the output down, e.g. close all connections.

        This is optional.

        """
