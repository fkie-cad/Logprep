"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

import typing
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
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(Output.Config, self._config)

    @property
    def default(self) -> bool:
        """returns the default parameter"""
        return self.config.default

    @property
    def metric_labels(self) -> dict:
        """Return the metric labels for this component."""
        return {
            "component": "output",
            "description": self.describe(),
            "type": self.config.type,
            "name": self.name,
        }

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
        try:
            return await self._store_batch(events, target)
        except Exception as error:
            self.metrics.number_of_errors += 1
            for event in events:
                self._handle_error(event, error)
            return events

    @abstractmethod
    async def _store_batch(
        self, events: Sequence[Event], target: str | None = None
    ) -> Sequence[Event]:
        """"""

    @staticmethod
    def _handle_error(event: Event, error: Exception) -> None:
        event.errors.append(error)

    @staticmethod
    def _handle_errors(func: Callable) -> Callable:
        """Decorator to handle errors during the store process."""

        async def wrapper(self, *args, **kwargs):
            event = args[0] if args else kwargs.get("event")
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:  # pylint: disable=broad-except
                event.errors.append(e)
                self.metrics.number_of_errors += 1
                # TODO convey error event
                # event.state.current_state = EventStateType.FAILED

        return wrapper
