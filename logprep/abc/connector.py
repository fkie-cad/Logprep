"""abstract module for connectors"""

from attrs import define, field

from logprep.metrics.metrics import CounterMetric, HistogramMetric
from logprep.ng.abc.component import NgComponent


class Connector(NgComponent):
    """Abstract Connector Class to define the Interface"""

    @define(kw_only=True)
    class Config(NgComponent.Config):
        """Configuration for the connector"""

    @define(kw_only=True)
    class Metrics(NgComponent.Metrics):
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

    async def setup(self) -> None:
        """Set up the connector."""

        await super().setup()

    async def shut_down(self) -> None:
        """Shutdown the connector and cleanup resources."""

        await super().shut_down()
