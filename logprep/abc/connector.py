""" abstract module for connectors"""
from logging import Logger
from attr import define
from logprep.abc import Component
from logprep.metrics.metric import Metric, calculate_new_average


class Connector(Component):
    """Abstract Connector Class to define the Interface"""

    @define(kw_only=True)
    class ConnectorMetrics(Metric):
        """Tracks statistics about this connector"""

        _prefix: str = "logprep_connector_"

        number_of_processed_events: int = 0
        """Number of events that were processed by the connector"""
        mean_processing_time_per_event: float = 0.0
        """Mean processing time for one event"""
        _mean_processing_time_sample_counter: int = 0
        """Helper to calculate mean processing time"""
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

    __slots__ = ["metrics", "metric_labels"]

    metrics: ConnectorMetrics
    metric_labels: dict

    def __init__(self, name: str, configuration: "Component.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self.metric_labels = self._config.metric_labels
        self.metric_labels.update(
            {"connector": "input" if self._config.type.endswith("_input") else "output"}
        )
        self.metrics = self.ConnectorMetrics(
            labels=self.metric_labels,
        )
