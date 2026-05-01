"""
DummyOutput
===========

The Dummy Output Connector can be used to store unmodified documents.
It only requires the connector type to be configured.

..  code-block:: yaml

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_dummy_output:
        type: dummy_output
"""

import logging
import typing
from collections.abc import Sequence
from typing import TYPE_CHECKING

from attrs import define, field, validators

from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output

if TYPE_CHECKING:
    from logprep.ng.abc.connector import Connector  # pragma: no cover

logger = logging.getLogger("DummyOutput")


class DummyOutput(Output):
    """
    A dummy output that stores unmodified documents unless an exception was raised.
    """

    @define(kw_only=True)
    class Config(Output.Config):
        """Common Configurations"""

        do_nothing: bool = field(default=False)
        """If set to True, this connector will behave completely neutral and not do anything.
        Especially counting metrics or storing events."""

        exceptions: list[str | None] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            default=[],
        )
        """List of exceptions to raise when storing an event. This is useful
        for testing purposes. If an exception is raised, the exception is handled
        by the output decorator.
        """

        reset_on_flush: bool = field(default=False)
        """If set to True, the stored events will be cleared when flush() is called."""

    _recorded_events: list[tuple[Event, str | None]]
    failed_events: list[Event]
    setup_called_count: int
    shut_down_called_count: int
    _exceptions: list[str | None]

    __slots__ = [
        "_recorded_events",
        "failed_events",
        "setup_called_count",
        "shut_down_called_count",
        "exceptions",
    ]

    def __init__(self, name: str, configuration: "DummyOutput.Config"):
        super().__init__(name, configuration)
        self._recorded_events = []
        self.failed_events = []
        self.shut_down_called_count = 0
        self.exceptions = configuration.exceptions

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("DummyOutput.Config", self._config)

    @property
    def events(self) -> Sequence[Event]:
        """Returns events stored in this output"""
        return [event for (event, _) in self._recorded_events]

    @property
    def events_with_targets(self) -> Sequence[tuple[Event, str | None]]:
        """Returns events stored and their respective target in this output"""
        return self._recorded_events

    async def _store_single(self, event: Event, target: str | None = None) -> None:
        """Store the document in the output destination.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.
        """
        if self.config.do_nothing:
            return
        try:
            if self.exceptions:
                exception = self.exceptions.pop(0)
                if exception is not None:
                    raise ValueError(exception)
            self._recorded_events.append((event, target))
            self.metrics.number_of_processed_events += 1
        except Exception as error:  # pylint: disable=W0718
            self.metrics.number_of_errors += 1
            self._handle_error(event, error)

    async def _store_batch(
        self, events: Sequence[Event], target: str | None = None
    ) -> Sequence[Event]:
        for event in events:
            try:
                await self._store_single(event, target)
            except Exception as error:
                pass  # TODO implement
        return events

    async def shut_down(self):
        self.shut_down_called_count += 1
        return await super().shut_down()
