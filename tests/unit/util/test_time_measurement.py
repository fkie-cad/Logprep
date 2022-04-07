from logprep.util.time_measurement import TimeMeasurement


class TestTimeMeasurement:

    def setup_method(self):
        self.event = {"test_key": "test_val"}

    @TimeMeasurement.measure_time("test")
    def dummy_method(self, event):
        return True

    @TimeMeasurement.measure_time("pipeline")
    def dummy_method_pipeline(self, event):
        return True

    def test_time_measurement_decorator_does_not_change_return(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        assert self.dummy_method(self.event)

    def test_time_measurement_decorator_appends_processing_times_to_event(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        self.dummy_method(self.event)
        processing_times = self.event.get("processing_times")
        assert processing_times
        timestamp = processing_times.get("test")
        assert timestamp is not None
        assert isinstance(timestamp, float)

    def test_deactivated_decorator_does_not_do_a_thing(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        TimeMeasurement.APPEND_TO_EVENT = False
        assert self.dummy_method(self.event)
        assert self.event.get("processing_times") is None

    def test_time_measurement_decorator_does_not_append_processing_times_to_event_if_deactivated(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = False
        result = self.dummy_method(self.event)
        assert (result is True)
        processing_times = self.event.get("processing_times")
        assert processing_times is None
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        TimeMeasurement.APPEND_TO_EVENT = False

    def test_time_measurement_decorator_is_parameterizable(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        self.dummy_method_pipeline(self.event)
        assert self.event.get("processing_times").get("pipeline") is not None
