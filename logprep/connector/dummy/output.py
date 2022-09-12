"""This module contains a dummy output that can be used for testing purposes."""
from logging import Logger
from typing import List

from attr import field, define
from attrs import validators

from logprep.abc.output import Output


class DummyOutput(Output):
    """
    A dummy output that stores unmodified documents unless an exception was raised.
    """

    @define(kw_only=True)
    class Config(Output.Config):
        """Common Configurations"""

        exceptions: List[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            default=[],
        )

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

    def __init__(
        self,
        name: str,
        configuration: "Connector.Config",
        logger: Logger,
    ):
        super().__init__(name, configuration, logger)
        self.events = []
        self.failed_events = []
        self.setup_called_count = 0
        self.shut_down_called_count = 0
        self._exceptions = configuration.exceptions

    def setup(self):
        self.setup_called_count += 1

    def store(self, document: dict):
        if self._exceptions:
            exception = self._exceptions.pop(0)
            if exception is not None:
                raise Exception(exception)
        self.events.append(document)
        self.metrics.number_of_processed_events += 1
        if self.input_connector:
            self.input_connector.batch_finished_callback()

    def store_custom(self, document: dict, target: str):
        self.store(document)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.failed_events.append((error_message, document_received, document_processed))

    def shut_down(self):
        self.shut_down_called_count += 1
