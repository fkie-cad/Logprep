from logprep.util.time_measurement import TimeMeasurement


class TestTimeMeasurement:
    @TimeMeasurement.measure_time('test')
    def dummy_method(self, event):
        return True

    @TimeMeasurement.measure_time('pipeline')
    def dummy_method_pipeline(self, event):
        return True

    def test_time_measurement(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        
        event = {'test_key': 'test_val'}
        result = self.dummy_method(event)
        assert(result is True)

        processing_times = event.get('processing_times')
        assert processing_times
        
        timestamp = processing_times.get('test')
        assert timestamp
        assert isinstance(timestamp, float)

        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False

    def test_time_measurement_with_pipeline(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True

        event = {'test_key': 'test_val', '@timestamp': '1970-01-01T00:00:00.000Z'}
        result = self.dummy_method_pipeline(event)
        assert(result is True)

        processing_times = event.get('processing_times')
        assert processing_times
        
        timestamp = processing_times.get('pipeline')
        assert timestamp
        assert isinstance(timestamp, float)
        
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
