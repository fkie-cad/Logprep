"""This module provides the abstract base class for all input endpoints.

New input endpoint types are created by implementing it.

"""

from abc import abstractmethod
from .connector import Connector


class InputError(BaseException):
    """Base class for Input related exceptions."""


class CriticalInputError(InputError):
    """A significant error occurred - log and don't process the event."""

    def __init__(self, message, raw_input):
        self.raw_input = raw_input
        super().__init__(message)


class FatalInputError(InputError):
    """Must not be catched."""


class WarningInputError(InputError):
    """May be catched but must be displayed to the user/logged."""


class SourceDisconnectedError(WarningInputError):
    """Lost (or failed to establish) contact with the source."""


class InfoInputError(InputError):
    """Informational exceptions, e.g. to inform that a timeout occurred"""


class Input(Connector):
    """Connect to a source for log data."""

    def setup(self):
        """Set the input up, e.g. connect to a database.

        This is optional.

        """

    @abstractmethod
    def get_next(self, timeout: float):
        """Return the next document, blocking if none is available.

        Parameters
        ----------
        timeout : float
           The time to wait for blocking.

        Returns
        -------
        input : dict
            Input log data.

        Raises
        ------
        TimeoutWhileWaitingForInputError
            After timeout (usually a fraction of seconds) if no input data was available by then.

        """

    def batch_finished_callback(self):
        """Can be called by output connectors after processing a batch of one or more records."""

    def shut_down(self):
        """Close the input down, e.g. close all connections.

        This is optional.

        """
