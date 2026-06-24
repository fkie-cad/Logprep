"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

import typing
from abc import abstractmethod
from collections.abc import Sequence
from typing import TypeVar

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.connector import Connector
from logprep.ng.abc.event import OutputEvent

Event = TypeVar("Event", bound=OutputEvent)


class OutputError(LogprepException):
    """Base class for Output related exceptions."""

    @classmethod
    def from_error(
        cls, connector: "Output", error: Exception, message: str | None = None
    ) -> "OutputError":
        connector.metrics.number_of_errors += 1
        if message is not None:
            return cls(f"{cls.__name__} in {connector.describe()}: {message}: {str(error)}")
        else:
            return cls(f"{cls.__name__} in {connector.describe()}: {str(error)}")

    @classmethod
    def from_message(cls, connector: "Output", message: str) -> "OutputError":
        connector.metrics.number_of_errors += 1
        return cls(f"{cls.__name__} in {connector.describe()}: {message}")


class CriticalOutputError(OutputError):
    """A significant error occurred - log and don't process the event."""


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

    @abstractmethod
    async def _store(self, events: Sequence[OutputEvent]) -> None:
        """"""

    async def store(self, events: Sequence[OutputEvent]) -> None:
        """Stores the events in the output destination.

        Parameters
        ----------
        events : Sequence[Event]
            Events to be stored.
        """
        try:
            await self._store(events)
        except Exception as error:
            for event in events:
                if not event.stored and not event.is_failed():
                    event.mark_failed(error)

        for event in events:
            if event.stored:
                self.metrics.number_of_processed_events += 1
            else:
                if not event.is_failed():
                    event.mark_failed(
                        CriticalOutputError.from_message(
                            self, "invariant broken; event neither failed nor stored after store"
                        )
                    )
                self.metrics.number_of_errors += 1

    @staticmethod
    def _handle_error(event: Event, error: Exception) -> None:
        event.mark_failed(error)
