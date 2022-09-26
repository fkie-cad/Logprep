# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import logging

from logprep.factory import Factory
from logprep.util.time_measurement import TimeMeasurement


class TestTimeMeasurement:
    def setup_method(self):
        self.event = {"test_key": "test_val"}

    @TimeMeasurement.measure_time("test")
    def dummy_method(self, event):  # pylint: disable=unused-argument
        return True

    @TimeMeasurement.measure_time("pipeline")
    def dummy_method_pipeline(self, event):  # pylint: disable=unused-argument
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

    def test_time_measurement_decorator_does_not_append_processing_times_to_event_if_deactivated(
        self,
    ):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = False
        result = self.dummy_method(self.event)
        assert result is True
        processing_times = self.event.get("processing_times")
        assert processing_times is None
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        TimeMeasurement.APPEND_TO_EVENT = False

    def test_time_measurement_decorator_is_parameterizable(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        self.dummy_method_pipeline(self.event)
        assert self.event.get("processing_times").get("pipeline") is not None

    def test_time_measurement_decorator_updates_processors_processing_time_statistic(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = False

        dropper_config = {
            "Dropper1": {
                "type": "dropper",
                "specific_rules": ["tests/testdata/unit/dropper/rules/specific/"],
                "generic_rules": ["tests/testdata/unit/dropper/rules/generic/"],
                "tree_config": "tests/testdata/unit/tree_config.json",
            }
        }

        dropper = Factory.create(
            dropper_config,
            logging.getLogger("test-logger"),
        )
        assert dropper.metrics.mean_processing_time_per_event == 0
        assert dropper.metrics._mean_processing_time_sample_counter == 0
        event = {"test": "event"}
        dropper.process(event)
        assert dropper.metrics.mean_processing_time_per_event > 0
        assert dropper.metrics._mean_processing_time_sample_counter == 1

    def test_time_measurement_decorator_updates_connectors_processing_time_statistic(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = False

        dummy_input_config = {"Dummy": {"type": "dummy_input", "documents": [{}, {}]}}

        dummy_input = Factory.create(
            dummy_input_config,
            logging.getLogger("test-logger"),
        )
        assert dummy_input.metrics.mean_processing_time_per_event == 0
        assert dummy_input.metrics._mean_processing_time_sample_counter == 0
        dummy_input.get_next(0.001)
        assert dummy_input.metrics.mean_processing_time_per_event > 0
        assert dummy_input.metrics._mean_processing_time_sample_counter == 1
