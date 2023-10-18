# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
from attr import field, define

from logprep.abc.component import Component
from logprep.metrics.metrics import HistogramMetric
from logprep.util.time_measurement import TimeMeasurement


class TestTimeMeasurement:

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        processing_time_per_event: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                description="Time in seconds that it took to process an event",
                name="processing_time_per_event",
            )
        )
        """Time in seconds that it took to process an event"""

    def setup_method(self):
        self.event = {"test_key": "test_val"}
        self.metrics = TestTimeMeasurement.Metrics(labels={"label": "test"})

    @TimeMeasurement.measure_time()
    def dummy_method(self, event):  # pylint: disable=unused-argument
        return event

    def test_time_measurement_decorator_does_not_change_return(self):
        assert self.dummy_method(self.event) == self.event
