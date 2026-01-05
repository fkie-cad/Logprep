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
from typing import TYPE_CHECKING

from attrs import define, field, validators

from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output
from logprep.ng.event.log_event import LogEvent

if TYPE_CHECKING:
    from logprep.abc.connector import Connector  # pragma: no cover

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

        exceptions: list[str] = field(
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

    events: list[LogEvent]
    failed_events: list[LogEvent]
    setup_called_count: int
    shut_down_called_count: int
    _exceptions: list

    __slots__ = [
        "events",
        "failed_events",
        "setup_called_count",
        "shut_down_called_count",
        "_exceptions",
    ]

    def __init__(self, name: str, configuration: "DummyOutput.Config"):
        super().__init__(name, configuration)
        self.events = []
        self.failed_events = []
        self.shut_down_called_count = 0
        self._exceptions = configuration.exceptions

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast("DummyOutput.Config", self._config)

    @Output._handle_errors
    def store(self, event: Event) -> None:
        """Store the document in the output destination.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.
        """
        if self.config.do_nothing:
            return
        event.state.next_state()
        if self._exceptions:
            exception = self._exceptions.pop(0)
            if exception is not None:
                raise Exception(exception)  # pylint: disable=broad-exception-raised
        self.events.append(event)
        event.state.next_state(success=True)
        self.metrics.number_of_processed_events += 1

    def store_custom(self, event: Event, target: str):
        """Store additional data in a custom location inside the output destination."""
        self.store(event)

    def flush(self):
        """Flush not implemented because it has no backlog."""
        if self.config.reset_on_flush:
            self.events.clear()
        logger.debug("DummyOutput flushed %s events", len(self.events))

    def shut_down(self):
        self.shut_down_called_count += 1
        return super().shut_down()
