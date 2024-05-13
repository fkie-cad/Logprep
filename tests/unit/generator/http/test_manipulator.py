# pylint: disable=missing-docstring
# pylint: disable=protected-access
from datetime import datetime, timedelta

import pytest

from logprep.generator.http.input import EventClassConfig
from logprep.generator.http.manipulator import Manipulator


@pytest.fixture(name="manipulator_with_timestamps")
def get_manipulator_with_timestamps():
    event_class_config = {
        "target_path": "/some/path",
        "timestamps": [
            {"key": "timestamp1", "format": "%Y%m%d"},
            {"key": "timestamp2", "format": "%Y%m%d-%H%M%S"},
        ],
    }
    config = EventClassConfig(**event_class_config)
    return Manipulator(
        config=config,
        replace_timestamp=True,
        tag="testtag",
    )


@pytest.fixture(name="manipulator_without_timestamps")
def get_manipulator_without_timestamps():
    event_class_config = {"target_path": "/some/path"}
    config = EventClassConfig(**event_class_config)
    return Manipulator(
        config=config,
        replace_timestamp=True,
        tag="testtag",
    )


class TestManipulator:
    def test_add_tags_if_no_tags_existed_yet(self, manipulator_with_timestamps):
        example_events = [{"event2": "something"}, {"event1": "something"}]
        example_event_with_tag = manipulator_with_timestamps.manipulate(example_events)
        assert example_event_with_tag[0]["tags"] == ["testtag"]
        assert example_event_with_tag[0] == example_events[0]
        assert example_event_with_tag[1]["tags"] == ["testtag"]
        assert example_event_with_tag[1] == example_events[1]

    def test_add_tags_appends_to_existing_tags(self, manipulator_with_timestamps):
        example_events = [
            {"event2": "something", "tags": ["some-tag"]},
            {"event1": "something", "tags": ["some-tag"]},
        ]
        example_event_with_tag = manipulator_with_timestamps.manipulate(example_events)
        assert example_event_with_tag[0]["tags"] == ["some-tag", "testtag"]
        assert example_event_with_tag[0] == example_events[0]
        assert example_event_with_tag[1]["tags"] == ["some-tag", "testtag"]
        assert example_event_with_tag[1] == example_events[1]

    def test_add_tags_kills_generator_if_tags_is_not_of_type_list(
        self, manipulator_with_timestamps
    ):
        example_events = [
            {"event2": "something", "tags": "some-tag"},
        ]
        with pytest.raises(ValueError, match="Can't set tags"):
            _ = manipulator_with_timestamps.manipulate(example_events)

    def test_timestamp_replacement_with_empty_timestamp_config(
        self, manipulator_without_timestamps
    ):
        example_events = [{"event2": "something"}, {"event1": "something"}]
        example_event_after_timestamps = manipulator_without_timestamps.manipulate(example_events)
        assert example_events == example_event_after_timestamps == example_events

    def test_timestamp_replacement_for_not_present_timestamp_field(
        self, manipulator_with_timestamps
    ):
        example_events = [{"event2": "something"}, {"event1": "something"}]
        example_event_after_timestamps = manipulator_with_timestamps.manipulate(example_events)

        assert example_events == example_event_after_timestamps

    def test_timestamp_replacement(self, manipulator_with_timestamps):
        example_event = {"timestamp1": "123", "any_field": "345"}
        example_event_after_timestamps = manipulator_with_timestamps._replace_timestamps(
            example_event
        )
        assert example_event["timestamp1"] != "123"
        assert example_event_after_timestamps["timestamp1"] != "123"

    def test_manipulate(self, manipulator_with_timestamps):
        example_events = [
            {"timestamp1": "123", "any_field": "345"},
            {"timestamp2": "123", "any_field": "abc"},
        ]
        manipulated_events = manipulator_with_timestamps.manipulate(example_events)
        assert manipulated_events[0]["tags"] == example_events[0]["tags"] == ["testtag"]
        assert manipulated_events[1]["tags"] == example_events[1]["tags"] == ["testtag"]
        assert manipulated_events[0]["timestamp1"] != "123"
        assert manipulated_events[1]["timestamp2"] == datetime.now().strftime("%Y%m%d-%H%M%S")

    @pytest.mark.parametrize(
        "time_shift_str, expected_time_delta_obj",
        [
            ("+0000", timedelta(hours=0, minutes=0)),
            ("-0000", -timedelta(hours=0, minutes=0)),
            ("+0200", timedelta(hours=2, minutes=0)),
            ("+0212", timedelta(hours=2, minutes=12)),
            ("-2012", -timedelta(hours=20, minutes=12)),
            ("-0002", -timedelta(hours=0, minutes=2)),
        ],
    )
    def test_run_manipulate_with_time_shift(self, time_shift_str, expected_time_delta_obj):
        event_class_config = {
            "target_path": "/some/path",
            "timestamps": [
                {"key": "timestamp", "format": "%Y%m%d-%H%M%S", "time_shift": time_shift_str},
            ],
        }
        config = EventClassConfig(**event_class_config)
        manipulator = Manipulator(
            config=config,
            replace_timestamp=True,
            tag="testtag",
        )
        example_events = [
            {"timestamp": "123", "any_field": "abc"},
        ]
        manipulated_events = manipulator.manipulate(example_events)
        assert manipulated_events[0]["timestamp"] == (
            datetime.now() + expected_time_delta_obj
        ).strftime("%Y%m%d-%H%M%S")
