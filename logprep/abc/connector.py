""" abstract module for connectors"""
import sys
from abc import ABC
from logging import Logger

from attr import define, field, validators
from logprep.metrics.metric import Metric, calculate_new_average
from logprep.util.helper import camel_to_snake


class Connector(ABC):
    """Abstract Connector Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config:
        """Common Configurations"""

        type: str = field(validator=validators.instance_of(str))

    @define(kw_only=True)
    class ConnectorMetrics(Metric):
        """Tracks statistics about this connector"""

        _prefix: str = "logprep_connector_"

        number_of_processed_events: int = 0
        """Number of events that were processed by the connector"""
        mean_processing_time_per_event: float = 0.0
        """Mean processing time for one event"""
        _mean_processing_time_sample_counter: int = 0
        number_of_warnings: int = 0
        """Number of warnings that occurred while processing events"""
        number_of_errors: int = 0
        """Number of errors that occurred while processing events"""

        def update_mean_processing_time_per_event(self, new_sample):
            """Updates the mean processing time per event"""
            new_avg, new_sample_counter = calculate_new_average(
                self.mean_processing_time_per_event,
                new_sample,
                self._mean_processing_time_sample_counter,
            )
            self.mean_processing_time_per_event = new_avg
            self._mean_processing_time_sample_counter = new_sample_counter

    __slots__ = ["name", "_logger", "_config", "metrics", "metric_labels"]

    if not sys.version_info.minor < 7:
        __slots__.append("__dict__")

    name: str
    metrics: ConnectorMetrics
    metric_labels: dict
    _logger: Logger
    _config: Config

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger):
        self._logger = logger
        self._config = configuration
        self.name = name

    def __repr__(self):
        return camel_to_snake(self.__class__.__name__)

    def describe(self) -> str:
        """Provide a brief name-like description of the connector.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> ConfluentKafkaInput(name)

        """
        return f"{self.__class__.__name__} ({self.name})"
