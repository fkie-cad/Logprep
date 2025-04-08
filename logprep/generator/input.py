"""
GeneratorInput
==============

This class generates events based on example events from jsonl files and
writes batches of them to a temporary directory for later loading.
"""

import logging
import shutil
import tempfile
import time
import warnings
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional

import msgspec
from attrs import define, field, validators
from ruamel.yaml import YAML

from logprep.generator.batcher import Batcher
from logprep.generator.manipulator import Manipulator

yaml = YAML(typ="safe")

logger = logging.getLogger("Input")


@define(kw_only=True)
class TimestampReplacementConfig:
    """Configuration Class fot TimestampReplacement"""

    key: str = field(validator=validators.instance_of(str))
    format: str = field(validator=validators.instance_of(str))
    time_shift: str = field(
        default="+0000",
        validator=(validators.instance_of(str), validators.matches_re(r"[+-]\d{4}")),
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

    target: Optional[str] = field(
        default=None, validator=validators.optional(validators.instance_of(str))
    )
    target_path: Optional[str] = field(
        default=None, validator=validators.optional(validators.instance_of(str))
    )

    timestamps: List[TimestampReplacementConfig] = field(
        default=[],
        converter=TimestampReplacementConfig.convert_list_of_dicts_to_objects,
        validator=validators.optional(
            validators.deep_iterable(
                member_validator=validators.instance_of(TimestampReplacementConfig)
            )
        ),
    )

    def __attrs_post_init__(self):
        if self.target is None and self.target_path is None:
            raise ValueError("Either 'target' or 'target_path' must be provided.")

        if self.target_path is not None:
            warnings.warn(
                "'target_path' is deprecated and will be removed in the future. "
                "Use 'target' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.target = self.target_path


class Input:
    """Input that first processes and manipulates the input dataset and then shuffles from it"""

    MAX_EVENTS_PER_FILE = 100_000

    @cached_property
    def temp_dir(self):
        """Create temporary directory and return path"""
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

    def __init__(self, config: dict) -> None:
        self.input_root_path = Path(config.get("input_dir"))
        self.file_loader = FileLoader(self.input_root_path)
        self.file_writer = FileWriter()
        self.log_class_manipulator_mapping: Dict = {}
        self.number_events_of_dataset = 0
        self.config = config
        self.target_sets: set = set()

    def reformat_dataset(self) -> None:
        """
        Collect all jsonl files of each event class and their corresponding manipulators
        and targets. The collected events will be written to one or multiple files containing
        the events and the target for the events.
        """
        logger.info(
            "Reading input dataset and creating temporary event collections in: '%s'", self.temp_dir
        )
        start_time = time.perf_counter()
        for event_class_dir in sorted(f.name for f in Path(self.input_root_path).iterdir()):
            file_paths, log_class_config = self.file_loader.retrieve_log_files(event_class_dir)
            self._set_manipulator(log_class_config)
            self._populate_events_list(file_paths, log_class_config)
        logger.info("Preparing data took: %s seconds", time.perf_counter() - start_time)

    def _populate_events_list(
        self, file_paths: list[Path], log_class_config: EventClassConfig
    ) -> None:
        """
        Collect the events from the dataset inside the events list. Each element will look like
        '<TARGET_PATH>,<JSONL-EVENT>\n', such that these lines can later be written to a file.
        """
        events = []
        for file in file_paths:
            with open(file, "r", encoding="utf8") as event_file:
                for event in event_file.readlines():
                    self.number_events_of_dataset += 1
                    self.target_sets.add(log_class_config.target)
                    events.append(f"{log_class_config.target},{event.strip()}")
                    if len(events) == self.MAX_EVENTS_PER_FILE:
                        self.file_writer.write_events_file(events, self.temp_dir, self.config)
                if events:
                    self.file_writer.write_events_file(events, self.temp_dir, self.config)

    def _set_manipulator(self, log_class_config: EventClassConfig) -> None:
        manipulator = Manipulator(
            log_class_config,
            self.config.get("replace_timestamp", True),
            self.config.get("tag", "loadtest"),
        )
        self.log_class_manipulator_mapping[log_class_config.target] = manipulator

    def clean_up_tempdir(self) -> None:
        """Delete temporary directory which contains the reformatted dataset"""
        if Path(self.temp_dir).exists() and Path(self.temp_dir).is_dir():
            shutil.rmtree(self.temp_dir)
        logger.info("Cleaned up temp dir: '%s'", self.temp_dir)


class FileLoader:
    """Read sample log events"""

    def __init__(self, input_root_path: Path, **config) -> None:
        self.input_root_path = input_root_path
        self.number_events_of_dataset = config.get("events")

    def retrieve_log_files(self, event_class_dir: Path) -> tuple[list[Path], EventClassConfig]:
        """Retrieve the file paths of all sample events of one log class,
        the log class configuration"""
        dir_path = self.input_root_path / event_class_dir
        log_class_config = self._load_event_class_config(dir_path)
        file_paths = [f for f in Path(dir_path).iterdir() if f.suffix == ".jsonl"]
        return file_paths, log_class_config

    def _load_event_class_config(self, event_class_dir_path: Path) -> EventClassConfig:
        """Load the event class specific configuration"""
        config_path = event_class_dir_path / "config.yaml"
        with open(config_path, "r", encoding="utf8") as file:
            event_class_config = yaml.load(file)
        logger.debug("Following class config was loaded: %s", event_class_config)
        event_class_config = EventClassConfig(**event_class_config)
        if "," in event_class_config.target:
            raise ValueError(
                f"InvalidConfiguration: No ',' allowed in target_path, {event_class_config}"
            )
        return event_class_config


class FileWriter:
    """Handles event file writing and shuffling."""

    def __init__(self):
        self.event_file_counter = 0

    def write_events_file(self, events: list[str], temp_dir: Path, config: Dict):
        """
        Take a list of target and event strings and write them to a file. If configured the events
        will be shuffled first.
        """
        file_name = f"logprep_input_data_{self.event_file_counter:0>4}.txt"
        temp_file_path = temp_dir / file_name
        batcher = Batcher(events, **config)
        with open(temp_file_path, "a", encoding="utf8") as event_file:
            event_file.writelines(batcher)
        events.clear()
        self.event_file_counter += 1
