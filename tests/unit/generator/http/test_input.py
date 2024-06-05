# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import os
import re
from collections import defaultdict

import msgspec
import pytest
import yaml

from logprep.generator.http.input import EventClassConfig, Input
from tests.unit.generator.http.util import create_test_event_files


class TestInput:
    def setup_method(self):
        self.test_url = "https://testdomain.de"
        config = {
            "target_url": self.test_url,
            "input_root_path": "",
            "batch_size": 50,
            "replace_timestamp": True,
            "tag": "loadtest",
        }
        self.input = Input(config=config)

    def test_load_parses_same_amount_of_events_as_the_batch_size(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 100
        batch_size = 100
        create_test_event_files(tmp_path, example_event, number_of_events)
        self.input.input_root_path = tmp_path
        self.input.batch_size = batch_size
        self.input.reformat_dataset()
        loader = self.input.load()
        _, events = next(loader)
        assert len(events) == number_of_events
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_parses_less_events_as_batch_size(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 3
        batch_size = 100
        create_test_event_files(tmp_path, example_event, number_of_events)
        self.input.input_root_path = tmp_path
        self.input.batch_size = batch_size
        self.input.reformat_dataset()
        loader = self.input.load()
        _, events = next(loader)
        assert len(events) == number_of_events
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_parses_more_events_as_batch_size(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 150
        batch_size = 100
        create_test_event_files(tmp_path, example_event, number_of_events)
        self.input.input_root_path = tmp_path
        self.input.batch_size = batch_size
        self.input.reformat_dataset()
        loader = self.input.load()
        _, first_batch_events = next(loader)
        assert len(first_batch_events) == 100
        _, second_batch_events = next(loader)
        assert len(second_batch_events) == 50
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_parses_more_events_as_batch_size_over_multiple_files(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 150
        batch_size = 100
        create_test_event_files(tmp_path, example_event, number_of_events, file_name="events.jsonl")
        create_test_event_files(
            tmp_path, example_event, number_of_events, file_name="events2.jsonl"
        )
        self.input.input_root_path = tmp_path
        self.input.batch_size = batch_size
        self.input.reformat_dataset()
        loader = self.input.load()
        _, first_batch = next(loader)
        assert len(first_batch) == 100
        _, second_batch = next(loader)
        assert len(second_batch) == 100
        _, third_batch = next(loader)
        assert len(third_batch) == 100
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_returns_smaller_than_configured_batch_at_end_of_event_class(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events_class_one = 50
        number_of_events_class_two = 150
        batch_size = 100
        create_test_event_files(
            tmp_path,
            example_event,
            number_of_events_class_one,
            file_name="events.jsonl",
            class_name="class_one",
        )
        create_test_event_files(
            tmp_path,
            example_event,
            number_of_events_class_two,
            file_name="events2.jsonl",
            class_name="class_two",
        )
        self.input.input_root_path = tmp_path
        self.input.batch_size = batch_size
        self.input.reformat_dataset()
        sum_of_all_events = 0
        loader = self.input.load()
        _, first_batch = next(loader)
        assert len(first_batch) == 50
        sum_of_all_events += len(first_batch)
        _, second_batch = next(loader)
        assert len(second_batch) == 50
        sum_of_all_events += len(second_batch)
        _, third_batch = next(loader)
        assert len(third_batch) == 100
        sum_of_all_events += len(third_batch)
        with pytest.raises(StopIteration):
            _ = next(loader)
        assert sum_of_all_events == number_of_events_class_one + number_of_events_class_two

    def test_load_parses_nothing_on_empty_dir(self, tmp_path):
        self.input.input_root_path = tmp_path
        loader = self.input.load()
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_parses_only_jsonl_files(self, tmp_path):
        create_test_event_files(tmp_path, {"some": "event"}, 150, file_name="event.json")
        self.input.input_root_path = tmp_path
        self.input.reformat_dataset()
        loader = self.input.load()
        with pytest.raises(StopIteration):
            _ = next(loader)

    def test_load_raises_parsing_error_on_invalid_jsons(self, tmp_path):
        event_class_dir = tmp_path / "test_class"
        os.makedirs(event_class_dir, exist_ok=True)
        events_file_path = event_class_dir / "events.jsonl"
        events = ['{"event":"one"}', '{"broken event"}', '{"event":"three"}']
        events_file_path.write_text("\n".join(events))
        event_class_config = {"target_path": "/target"}
        config_file_path = event_class_dir / "config.yaml"
        config_file_path.write_text(yaml.dump(event_class_config))
        self.input.input_root_path = tmp_path
        self.input.reformat_dataset()
        loader = self.input.load()
        with pytest.raises(msgspec.DecodeError, match="JSON is malformed: expected ':'"):
            _ = next(loader)

    def test_target_changes_between_event_classes(self, tmp_path):
        class_one_config = {"target_path": "/target-one"}
        class_two_config = {"target_path": "/target-two"}
        create_test_event_files(
            tmp_path, {"some": "event"}, 50, class_name="test_class_one", config=class_one_config
        )
        create_test_event_files(
            tmp_path, {"some": "event"}, 50, class_name="test_class_two", config=class_two_config
        )
        self.input.input_root_path = tmp_path
        self.input.reformat_dataset()
        loader = self.input.load()
        target, events = next(loader)
        assert len(events) == 50
        assert target == "/target-one"
        target, events = next(loader)
        assert len(events) == 50
        assert target == "/target-two"

    @pytest.mark.parametrize(
        "config, expected_error, error_message",
        [
            (
                {"target_path": "/system/", "timestamps": [{"key": "foo", "format": "%Y%m%d"}]},
                None,
                None,
            ),
            (
                {"target": "/system/", "timestamps": [{"key": "foo", "format": "%Y%m%d"}]},
                TypeError,
                "got an unexpected keyword argument 'target'",
            ),
            (
                {"target_path": 3, "timestamps": [{"key": "foo", "format": "%Y%m%d"}]},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {"target_path": "/foo", "timestamp": [{"key": "foo", "format": "%Y%m%d"}]},
                TypeError,
                "got an unexpected keyword argument 'timestamp'",
            ),
            (
                {"target_path": "/foo", "timestamps": [{"format": "%Y%m%d"}]},
                TypeError,
                "missing 1 required keyword-only argument: 'key'",
            ),
            (
                {"target_path": "/foo", "timestamps": [{"key": "foo", "something": "%Y%m%d"}]},
                TypeError,
                "got an unexpected keyword argument 'something'",
            ),
            (
                {"target_path": "/foo", "timestamps": [{"key": "foo"}]},
                TypeError,
                "missing 1 required keyword-only argument: 'format'",
            ),
            (
                {
                    "target_path": "/foo",
                    "timestamps": [{"key": "foo", "format": "%Y%m%d", "time_shift": 12}],
                },
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {
                    "target_path": "/foo",
                    "timestamps": [{"key": "foo", "format": "%Y%m%d", "time_shift": "12"}],
                },
                ValueError,
                "'time_shift' must match regex",
            ),
            (
                {
                    "target_path": "/foo",
                    "timestamps": [{"key": "foo", "format": "%Y%m%d", "time_shift": "a0200"}],
                },
                ValueError,
                "'time_shift' must match regex",
            ),
            (
                {
                    "target_path": "/foo",
                    "timestamps": [{"key": "foo", "format": "%Y%m%d", "time_shift": "+0200"}],
                },
                None,
                None,
            ),
            (
                {
                    "target_path": "/foo",
                    "timestamps": [{"key": "foo", "format": "%Y%m%d", "time_shift": "-0200"}],
                },
                None,
                None,
            ),
        ],
    )
    def test_event_class_config_validation(self, config, expected_error, error_message):
        if expected_error:
            with pytest.raises(expected_error, match=re.escape(error_message)):
                _ = EventClassConfig(**config)
        else:
            EventClassConfig(**config)

    def test_load_returns_events_in_sorted_order(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 150
        dataset_path = tmp_path / "dataset"
        create_test_event_files(
            dataset_path,
            example_event,
            number_of_events,
            file_name="events.jsonl",
            class_name="class-one",
        )
        create_test_event_files(
            dataset_path,
            example_event,
            number_of_events,
            file_name="events2.jsonl",
            class_name="class-two",
        )
        batch_size = 100
        self.input.input_root_path = dataset_path
        self.input.batch_size = batch_size
        self.input._temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.input._temp_dir, exist_ok=True)
        self.input.reformat_dataset()
        event_id = 0
        previous_event_id = -1  # count through event id's and check if they always increase
        expected_target = "/target-class-one"
        for target, events in self.input.load():
            assert target == expected_target
            for event in events:
                event_id = event.get("id")
                assert event_id > previous_event_id
                previous_event_id = event_id
            if event_id == 149:  # end of first log class reached (resetting for second class)
                previous_event_id = -1
                expected_target = "/target-class-two"

    def test_load_returns_event_in_shuffled_order(self, tmp_path):
        example_event = {"some": "event"}
        number_of_events = 150
        dataset_path = tmp_path / "dataset"
        create_test_event_files(
            dataset_path,
            example_event,
            number_of_events,
            file_name="events.jsonl",
            class_name="class-one",
        )
        create_test_event_files(
            dataset_path,
            example_event,
            number_of_events,
            file_name="events2.jsonl",
            class_name="class-two",
        )
        batch_size = 100
        self.input.input_root_path = dataset_path
        self.input.batch_size = batch_size
        self.input.config.update({"shuffle": True})
        self.input._temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.input._temp_dir, exist_ok=True)
        self.input.reformat_dataset()
        target_event_ids = defaultdict(list)
        for target, events in self.input.load():
            for event in events:
                target_event_ids[target].append(event.get("id"))
        for target, event_ids in target_event_ids.items():
            is_sorted = all(a <= b for a, b in zip(event_ids, event_ids[1:]))
            assert not is_sorted, f"Target {target} is sorted"

    def test_raise_value_error_on_comma_in_target_path(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        create_test_event_files(
            dataset_path,
            sample_event={"some": "event"},
            number_of_events=150,
            file_name="events.jsonl",
            class_name="class,one",
        )
        self.input.input_root_path = dataset_path
        with pytest.raises(ValueError, match="No ',' allowed in target_path"):
            self.input.reformat_dataset()

    def test_created_temp_files_are_split_when_max_events_per_file_limit_is_reached(self, tmp_path):
        event_limit_per_file = self.input.MAX_EVENTS_PER_FILE
        dataset_path = tmp_path / "dataset"
        for i in range(4):  # create four log classes with one third of the event_limit_per_file
            create_test_event_files(
                dataset_path,
                sample_event={"some": "event"},
                number_of_events=int(event_limit_per_file / 3),
                file_name=f"events-{i}.jsonl",
                class_name=f"class-{i}",
            )
        self.input.input_root_path = dataset_path
        self.input._temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.input._temp_dir, exist_ok=True)
        self.input.reformat_dataset()
        created_temp_files = [file for file in os.listdir(self.input._temp_dir)]
        assert len(created_temp_files) > 1
        for filename in created_temp_files:
            path = self.input._temp_dir / filename
            with open(path, "r", encoding="utf8") as file:
                lines = len(file.readlines())
                assert lines <= event_limit_per_file, path

    def test_configuring_an_events_limit_will_iterate_over_the_dataset_until_this_limit_is_reached(
        self, tmp_path
    ):
        config = {
            "target_url": self.test_url,
            "input_root_path": "",
            "batch_size": 77,  # take an odd number so the batchsize will exceed the event limit
            "replace_timestamp": True,
            "tag": "loadtest",
            "events": 1_000,
        }
        self.input = Input(config=config)
        dataset_path = tmp_path / "dataset"
        create_test_event_files(
            dataset_path,
            sample_event={"some": "event"},
            number_of_events=100,
            file_name=f"events.jsonl",
            class_name=f"class-one",
        )
        self.input.input_root_path = dataset_path
        self.input._temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.input._temp_dir, exist_ok=True)
        self.input.reformat_dataset()
        event_counter = 0
        for target, events in self.input.load():
            event_counter += len(events)
        assert event_counter == config.get("events")
