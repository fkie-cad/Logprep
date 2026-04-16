"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

from abc import abstractmethod
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Callable

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.connector import Connector
from logprep.ng.abc.event import Event


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
    class Metrics(Connector.Metrics):
        """Tracks statistics about this connector"""

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
    async def store(self, event: Event) -> None:
        """Store the event in the output destination.

        Parameters
        ----------
        event : Event
           Processed log event that will be stored.
        """

    @abstractmethod
    async def store_custom(self, event: Event, target: str) -> None:
        """Store the event in the output destination.

        Parameters
        ----------
        event : Event
           Processed log event that will be stored.
        target : str
            Custom target for the event.
        """

    @abstractmethod
    async def store_batch(
        self, events: Sequence[Event], target: str | None = None
    ) -> Sequence[Event]:
        """Stores the events in the output destination.

        Parameters
        ----------
        events : Sequence[Event]
            Events to be stored.
        target : str | None
            Custom target for the events, defaults to None

        Returns
        -------
        Sequence[Event]
            Events after sending.
        """

    @abstractmethod
    async def flush(self):
        """Write the backlog to the output destination.
        Needs to be implemented in child classes to ensure
        that the backlog is written to the output destination.
        """

    @staticmethod
    def _handle_errors(func: Callable) -> Callable:
        """Decorator to handle errors during the store process."""

        def wrapper(self, *args, **kwargs):
            event = args[0] if args else kwargs.get("event")
            try:
                func(self, *args, **kwargs)
            except Exception as e:  # pylint: disable=broad-except
                event.errors.append(e)
                self.metrics.number_of_errors += 1
                # TODO convey error event
                # event.state.current_state = EventStateType.FAILED

        return wrapper

    async def setup(self) -> None:
        """Set up the output connector."""

        await super().setup()

    async def shut_down(self) -> None:
        """Shut down the output connector and cleanup resources."""

        await self.flush()
        await super().shut_down()
