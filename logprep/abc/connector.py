""" abstract module for connectors"""

from attrs import define, field

from logprep.abc.component import Component
from logprep.metrics.metrics import CounterMetric, HistogramMetric


class Connector(Component):
    """Abstract Connector Class to define the Interface"""

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """Tracks statistics about this connector"""

        number_of_processed_events: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of successful events",
                name="number_of_processed_events",
            )
        )
        """Number of successful events"""

        processing_time_per_event: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                description="Time in seconds that it took to store an event",
                name="processing_time_per_event",
            )
        )
        """Time in seconds that it took to process an event"""

        number_of_warnings: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of warnings that occurred while storing events",
                name="number_of_warnings",
            )
        )
        """Number of warnings that occurred while processing events"""

        number_of_errors: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of errors that occurred while storing events",
                name="number_of_errors",
            )
        )
        """Number of errors that occurred while processing events"""
