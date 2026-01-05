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

from logprep.abc.output import Output

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
        for testing purposes.
        """

        timeout: int = field(validator=validators.instance_of(int), default=500)
        """(Optional) Timeout for the connection (default is 500s)."""

    events: list
    failed_events: list
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
        self._schedule_task(task=self._flush, seconds=configuration.timeout)

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast("DummyOutput.Config", self._config)

    def store(self, document: dict):
        """Store the document in the output destination.

        Parameters
        ----------
        document : dict
           Processed log event that will be stored.
        """
        if self.config.do_nothing:
            return
        if self._exceptions:
            exception = self._exceptions.pop(0)
            if exception is not None:
                raise Exception(exception)  # pylint: disable=broad-exception-raised
        self.events.append(document)
        self.metrics.number_of_processed_events += 1

    def store_custom(self, document: dict, target: str):
        """Store additional data in a custom location inside the output destination."""
        self.store(document)

    def _flush(self):
        logger.debug("Flushing DummyOutput '%s' with %d events", self.name, len(self.events))

    def shut_down(self):
        self.shut_down_called_count += 1
        return super().shut_down()
