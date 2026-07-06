# pylint: disable=line-too-long

"""This module provides the abstract base class for all input endpoints.
New input endpoint types are created by implementing it.
"""

import logging
import typing
from abc import abstractmethod
from collections.abc import AsyncIterator, Sequence

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException
from logprep.metrics.metrics import Metric
from logprep.ng.abc.connector import Connector
from logprep.ng.abc.event import AcknowledgableEvent, ErrorEvent, LogEvent
from logprep.ng.util.preprocessor import PreprocessingError, Preprocessor
from logprep.util.converters import convert_from_dict
from logprep.util.preprocessor import PreprocessingConfig

logger = logging.getLogger("Input")


class InputError(LogprepException):
    """Base class for Input related exceptions."""

    @classmethod
    def from_error(
        cls, connector: "Input", error: Exception, message: str | None = None
    ) -> "InputError":
        connector.metrics.number_of_errors += 1
        if message is not None:
            return cls(f"{cls.__name__} in {connector.description}: {message}: {str(error)}")
        else:
            return cls(f"{cls.__name__} in {connector.description}: {str(error)}")

    @classmethod
    def from_message(cls, connector: "Input", message: str) -> "InputError":
        connector.metrics.number_of_errors += 1
        return cls(f"{cls.__name__} in {connector.description}: {message}")


class CriticalInputError(InputError):
    """A significant error occurred - log and don't process the event."""


class CriticalInputParsingError(CriticalInputError):
    """The input couldn't be parsed correctly."""


class FatalInputError(InputError):
    """Must not be catched."""


class InputWarning(LogprepException):
    """May be catched but must be displayed to the user/logged."""

    @classmethod
    def from_error(
        cls, connector: "Input", error: Exception, message: str | None = None
    ) -> "InputWarning":
        """Generate an `InputWarning` from a low level error"""
        connector.metrics.number_of_warnings += 1
        if message is not None:
            return cls(f"{cls.__name__} in {connector.description}: {message}: {str(error)}")
        else:
            return cls(f"{cls.__name__} in {connector.description}: {str(error)}")

    @classmethod
    def from_message(cls, connector: "Input", message: str) -> "InputWarning":
        """Generate an `InputWarning` from a message"""
        connector.metrics.number_of_warnings += 1
        return cls(f"{cls.__name__} in {connector.description}: {message}")


# =====================================================================================================================


class Input(Connector, AsyncIterator[LogEvent | ErrorEvent | None]):
    """Connect to a source for log data."""

    class Metrics(Connector.Metrics):
        """Input Metrics"""

    @define(kw_only=True, slots=False)
    class Config(Connector.Config):
        """Input Configurations"""

        preprocessing: PreprocessingConfig = field(
            validator=validators.instance_of(PreprocessingConfig),
            converter=lambda d: convert_from_dict(PreprocessingConfig, d),
            factory=PreprocessingConfig,
        )
        """
        See :class:`.PreprocessingConfig` for further details.
        """

        timeout: float = field(
            validator=(validators.instance_of(float), validators.gt(0)), default=5.0, eq=False
        )

    def __init__(self, name: str, configuration: "Input.Config") -> None:
        super().__init__(name, configuration)
        self.preprocessor = Preprocessor(
            configuration.preprocessing,
            self._decoder,
            self._encoder,
        )

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(Input.Config, self._config)

    @abstractmethod
    async def acknowledge(self, events: Sequence[AcknowledgableEvent]) -> None:
        """Acknowledge all delivered events."""

    @property
    def metric_labels(self) -> dict:
        """Return the metric labels for this component."""
        return {
            "component": "input",
            "description": self.description,
            "type": self.config.type,
            "name": self.name,
        }

    @abstractmethod
    async def _get_event(self, timeout: float) -> LogEvent | ErrorEvent | None:
        """Implements the details how to get the event

        Parameters
        ----------
        timeout : float
            timeout

        Returns
        -------
        LogEvent | ErrorEvent | None
        """

    @Metric.measure_time_async()
    async def get_next(self, timeout: float) -> LogEvent | ErrorEvent | None:
        """Return the next document

        Parameters
        ----------
        timeout : float
           The time to wait for blocking.

        Returns
        -------
        input : LogEvent, None
            Input log data.
        """
        try:
            event = await self._get_event(timeout)
        except CriticalInputError as error:
            # TODO error has not been catched; might be an upstream issue which needs retrying and backoff
            raise error

        if event is None or isinstance(event, ErrorEvent):
            return event

        try:
            await self.preprocessor.preprocess(event)
        except PreprocessingError as error:
            logger.error("Error during preprocessing", exc_info=error)
            event.mark_failed(error)
            return ErrorEvent.from_failed_event(event)

        self.metrics.number_of_processed_events += 1

        return event

    async def __anext__(self) -> LogEvent | ErrorEvent | None:
        """Return the next event in the Input Connector within the configured timeout.

        Returns
        -------
        LogEvent | ErrorEvent | None
            The next event retrieved from the underlying data source.
        """
        return await self.get_next(timeout=self.config.timeout)
