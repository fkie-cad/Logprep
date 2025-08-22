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

from typing import TYPE_CHECKING, List

from attr import define, field
from attrs import validators

from logprep.abc.event import Event
from logprep.event.log_event import LogEvent
from logprep.ng.abc.output import Output

if TYPE_CHECKING:
    from logprep.abc.connector import Connector  # pragma: no cover


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

        exceptions: List[str] = field(
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

    def __init__(self, name: str, configuration: "Connector.Config"):
        super().__init__(name, configuration)
        self.events = []
        self.failed_events = []
        self.shut_down_called_count = 0
        self._exceptions = configuration.exceptions

    @Output._handle_errors
    def store(self, event: Event) -> None:
        """Store the document in the output destination.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.
        """
        if self._config.do_nothing:
            return
        event.state.next_state()
        if self._exceptions:
            exception = self._exceptions.pop(0)
            if exception is not None:
                raise Exception(exception)  # pylint: disable=broad-exception-raised
        self.events.append(event)
        event.state.next_state(success=True)
        self.metrics.number_of_processed_events += 1

    def store_custom(self, event: Event, target: str):  # pylint: disable=unused-argument
        """Store additional data in a custom location inside the output destination."""
        self.store(event)

    def shut_down(self):
        self.shut_down_called_count += 1
        super().shut_down()

    def flush(self):
        """Flush not implemented because it has not backlog."""
