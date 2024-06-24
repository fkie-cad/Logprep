"""Input module that loads the jsonl files batch-wise"""

import itertools
import logging
import os
import random
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from functools import cached_property
from operator import itemgetter
from pathlib import Path
from typing import Generator, List

import msgspec
import yaml
from attr import define, field, validators

from logprep.generator.http.manipulator import Manipulator


@define(kw_only=True)
class TimestampReplacementConfig:
    """Configuration Class fot TimestampReplacement"""

    key: str = field(validator=[validators.instance_of(str)])
    format: str = field(validator=validators.instance_of(str))
    time_shift: str = field(
        default="+0000",
        validator=[validators.instance_of(str), validators.matches_re(r"[+-]\d{4}")],
    )
    time_delta: timedelta = field(
        default=None, validator=validators.optional(validators.instance_of(timedelta))
    )

    def __attrs_post_init__(self):
        """Converts the time_shift str +HHMM into a timedelta object"""
        sign = self.time_shift[0]
        time_str = self.time_shift[1:]
        parsed_time = datetime.strptime(time_str, "%H%M")
        time_delta = timedelta(hours=parsed_time.hour, minutes=parsed_time.minute)
        if sign == "+":
            self.time_delta = time_delta
        else:
            self.time_delta = -time_delta

    @staticmethod
    def convert_list_of_dicts_to_objects(dict_configs):
        """
        Converts a list of timestamp config dictionaries into a list
        of TimestampReplacementConfig Objects
        """
        configs = []
        for config_dict in dict_configs:
            configs.append(TimestampReplacementConfig(**config_dict))
        return configs


@define(kw_only=True)
class EventClassConfig:
    """Configuration for an event class"""

    target_path: str = field(validator=validators.instance_of(str))
    timestamps: List[TimestampReplacementConfig] = field(
        default=[],
        converter=TimestampReplacementConfig.convert_list_of_dicts_to_objects,
        validator=validators.optional(
            validators.deep_iterable(
                member_validator=validators.instance_of(TimestampReplacementConfig)
            )
        ),
    )


class Input:
    """Input that first processes and manipulates the input dataset and then shuffles from it"""

    MAX_EVENTS_PER_FILE = 100_000

    @cached_property
    def _temp_dir(self):
        return Path(tempfile.mkdtemp(prefix="logprep_"))

    @cached_property
    def _encoder(self):
        return msgspec.json.Encoder()

    @cached_property
    def _decoder(self):
        return msgspec.json.Decoder()

    @cached_property
    def _temp_filename_prefix(self):
        return "logprep_input_data"

    def __init__(self, config: dict):
        self.config = config
        self.input_root_path = config.get("input_dir")
        self.number_of_events = config.get("events")
        self.events_sent = 0
        self.batch_size = config.get("batch_size")
        self.log = logging.getLogger("Input")
        self.log_class_manipulator_mapping = {}
        self.number_events_of_dataset = 0
        self.event_file_counter = 0

    def reformat_dataset(self):
        """
        Collect all jsonl files of each event class and their corresponding manipulators
        and targets. The collected events will be written to one or multiple files containing
        the events and the target for the events.
        """
        self.log.info(
            "Reading input dataset and creating temporary event collections in: '%s'",
            self._temp_dir,
        )
        start_time = time.perf_counter()
        events = []
        event_classes = os.listdir(self.input_root_path)
        event_classes = sorted(event_classes)
        for event_class_dir in event_classes:
            file_paths, log_class_config = self._retrieve_log_files(event_class_dir)
            self._populate_events_list(events, file_paths, log_class_config)
        if events:
            self._write_events_file(events)
        self.log.info(f"Preparing data took: {time.perf_counter() - start_time:0.4f} seconds")

    def _retrieve_log_files(self, event_class_dir):
        """
        Retrieve the file paths of all sample events of one log class, the log class configuration
        and initialize the log class manipulator.
        """
        dir_path = os.path.join(self.input_root_path, event_class_dir)
        log_class_config = self._load_event_class_config(dir_path)
        manipulator = Manipulator(
            log_class_config, self.config.get("replace_timestamp"), self.config.get("tag")
        )
        self.log_class_manipulator_mapping.update({log_class_config.target_path: manipulator})
        file_paths = [
            os.path.join(dir_path, file_path)
            for file_path in os.listdir(dir_path)
            if file_path.endswith(".jsonl")
        ]
        return file_paths, log_class_config

    def _load_event_class_config(self, event_class_dir_path: str) -> EventClassConfig:
        """Load the event class specific configuration"""
        config_path = os.path.join(event_class_dir_path, "config.yaml")
        with open(config_path, "r", encoding="utf8") as file:
            event_class_config = yaml.safe_load(file)
        self.log.debug("Following class config was loaded: %s", event_class_config)
        event_class_config = EventClassConfig(**event_class_config)
        if "," in event_class_config.target_path:
            raise ValueError(
                f"InvalidConfiguration: No ',' allowed in target_path, {event_class_config}"
            )
        return event_class_config

    def _populate_events_list(self, events, file_paths, log_class_config):
        """
        Collect the events from the dataset inside the events list. Each element will look like
        '<TARGET_PATH>,<JSONL-EVENT>\n', such that these lines can later be written to a file.
        """
        for file in file_paths:
            with open(file, "r", encoding="utf8") as event_file:
                for event in event_file.readlines():
                    self.number_events_of_dataset += 1
                    events.append(f"{log_class_config.target_path},{event.strip()}\n")
                    if len(events) == self.MAX_EVENTS_PER_FILE:
                        self._write_events_file(events)

    def _write_events_file(self, events):
        """
        Take a list of target and event strings and write them to a file. If configured the events
        will be shuffled first.
        """
        if self.config.get("shuffle"):
            random.shuffle(events)
        file_name = f"{self._temp_filename_prefix}_{self.event_file_counter:0>4}.txt"
        temp_file_path = self._temp_dir / file_name
        with open(temp_file_path, "w", encoding="utf8") as event_file:
            event_file.writelines(events)
        self.event_file_counter += 1
        events.clear()

    def load(self) -> Generator[List, None, None]:
        """
        Generator that parses the next batch of events, manipulates them according to their
        respective configuration and returns them with their target.
        """
        input_files = [self._temp_dir / file for file in os.listdir(self._temp_dir)]
        if self.config.get("shuffle"):
            random.shuffle(input_files)
        if self.number_of_events is None:
            yield from self._load_all_once(input_files)
        else:
            yield from self._infinite_load(input_files)

    def _load_all_once(self, input_files):
        """Will iterate over all events once, if end is reached this generator stops."""
        events = []
        for event_file in input_files:
            with open(event_file, "r", encoding="utf8") as file:
                for line in file:
                    events.append(self._process_event_line(line))
                    if len(events) == self.batch_size:
                        yield from self._create_request_data(events)
                        events.clear()
        yield from self._create_request_data(events)

    def _create_request_data(self, event_batch):
        """Reformat a batch of events to a html payload string"""
        if self.config.get("shuffle"):
            event_batch = sorted(event_batch, key=lambda x: x[0])
        log_classes = itertools.groupby(event_batch, key=lambda x: x[0])
        for target_path, events in log_classes:
            yield target_path, list(map(itemgetter(1), events))

    def _process_event_line(self, line):
        """
        Parse an event line from file, apply manipulator and return the event and the corresponding
        target.
        """
        class_target, event = line.split(",", maxsplit=1)
        parsed_event = self._decoder.decode(event)
        manipulator = self.log_class_manipulator_mapping.get(class_target)
        manipulated_event = manipulator.manipulate([parsed_event])[0]
        return class_target, manipulated_event

    def _infinite_load(self, input_files):
        events = []
        for event_file in itertools.cycle(input_files):
            with open(event_file, "r", encoding="utf8") as file:
                for line in file:
                    if self.events_sent == self.number_of_events:
                        return
                    events.append(self._process_event_line(line))
                    if len(events) < self.batch_size:
                        continue
                    if self.events_sent + len(events) > self.number_of_events:
                        diff = self.number_of_events - self.events_sent
                        events = events[:diff]
                    self.events_sent += len(events)
                    yield from self._create_request_data(events)
                    events.clear()

    def clean_up_tempdir(self):
        """Delete temporary directory which contains the reformatted dataset"""
        if os.path.exists(self._temp_dir) and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir)
        self.log.info("Cleaned up temp dir: '%s'", self._temp_dir)
