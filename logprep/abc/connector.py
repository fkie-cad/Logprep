""" abstract module for connectors"""
from attr import define

from logprep.abc.component import Component
from logprep.metrics.metrics import calculate_new_average


class Connector(Component):
    """Abstract Connector Class to define the Interface"""

    @define(kw_only=True)
    class ConnectorMetrics(Component.Metrics):
        """Tracks statistics about this connector"""

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

    __slots__ = ["metrics"]

    metrics: ConnectorMetrics
