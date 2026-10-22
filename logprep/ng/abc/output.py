"""This module provides the abstract base class for all output endpoints.
New output endpoint types are created by implementing it.
"""

import typing
from abc import abstractmethod
from collections.abc import Sequence

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.connector import Connector
from logprep.ng.abc.event import LogEvent, OutputEvent
from logprep.util.helper import add_fields_to


class OutputError(LogprepException):
    """Base class for Output related exceptions."""

    @classmethod
    def from_error(
        cls, connector: "Output", error: Exception, message: str | None = None
    ) -> "OutputError":
        """Generate an `OutputException` from a low level error"""
        connector.metrics.number_of_errors.inc(1)
        if message is not None:
            return cls(f"{cls.__name__} in {connector.description}: {message}: {str(error)}")
        return cls(f"{cls.__name__} in {connector.description}: {str(error)}")

    @classmethod
    def from_message(cls, connector: "Output", message: str) -> "OutputError":
        """Generate an `OutputException` from a message"""
        connector.metrics.number_of_errors.inc(1)
        return cls(f"{cls.__name__} in {connector.description}: {message}")


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

        target_id_field: str = field(
            validator=validators.instance_of(str), default="@metadata.event.id"
        )
        """
        Defines the dotted field in which the event ID is stored for log messages delivered
        to this output. The default is :code:`@metadata.event.id`.
        An existing value at this field is overwritten. Parent fields that are not dictionaries
        are replaced by dictionaries to create the target field.
        If no event ID was assigned during input preprocessing, the target field is unchanged.
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
            "description": self.description,
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
            # TODO ensure to retry forever for retryable errors
            for event in events:
                if isinstance(event, LogEvent) and event.event_id is not None:
                    # If multiple outputs are served, this wouldnt work correctly if multiple target_id_field are set,
                    # as stale data would be retained
                    add_fields_to(
                        event.data,
                        {self.config.target_id_field: event.event_id},
                        overwrite_target=True,
                    )
            await self._store(events)
        except Exception as error:
            for event in events:
                if not event.stored and not event.is_failed():
                    event.mark_failed(error)

        for event in events:
            if not event.stored and not event.is_failed():
                event.mark_failed(
                    CriticalOutputError.from_message(
                        self, "invariant broken; event neither failed nor stored after store"
                    )
                )

        # modify metrics in batches
        self.metrics.number_of_processed_events.inc(sum(1 for e in events if e.stored))
        self.metrics.number_of_errors.inc(sum(1 for e in events if e.is_failed()))

    @staticmethod
    def _handle_error(event: OutputEvent, error: Exception) -> None:
        event.mark_failed(error)
