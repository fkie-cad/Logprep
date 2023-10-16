# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
from logprep.util.time_measurement import TimeMeasurement


class TestTimeMeasurement:
    def setup_method(self):
        self.event = {"test_key": "test_val"}

    @TimeMeasurement.measure_time("test")
    def dummy_method(self, event):  # pylint: disable=unused-argument
        return True

    def test_time_measurement_decorator_does_not_change_return(self):
        assert self.dummy_method(self.event)
