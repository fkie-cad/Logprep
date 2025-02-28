"""Input module that loads the jsonl files batch-wise"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from attrs import define, field, validators
from ruamel.yaml import YAML

from logprep.generator.http.batcher import Batcher
from logprep.generator.http.manipulator import Manipulator

yaml = YAML(typ="safe")

logger = logging.getLogger("Input")


@define(kw_only=True)
class TimestampReplacementConfig:
    """Configuration Class fot TimestampReplacement"""

    key: str = field(validator=(validators.instance_of(str)))
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

    def __init__(self, file_loader, manipulator, file_writer, config: dict) -> None:
        self.file_loader = file_loader
        self.manipulator = manipulator
        self.batcher = Batcher(config.get("batchsize"), events=config.get("events"))
        self.file_writer = file_writer
        self.config = config
        self.log_class_manipulator_mapping: Dict = {}

    def create_input(self):
        """Creates input"""
        _file_paths, log_class_config = self.file_loader.retrieve_log_files()
        self.manipulator.reformate_dateset()
        manipulator = Manipulator(
            log_class_config, self.config.get("replace_timestamp"), self.config.get("tag")
        )
        self.log_class_manipulator_mapping.update({log_class_config.target_path: manipulator})
        # self.batcher.batch()
        self.file_writer.write()
        while True:
            next(self.batcher)


class FileLoader:
    """Read sample log events"""

    MAX_EVENTS_PER_FILE = 100_000

    def __init__(self, input_root_path: Path, **config) -> None:
        self.input_root_path = input_root_path
        self.number_events_of_dataset = config.get("events")

    def retrieve_log_files(self, event_class_dir: Path):
        """Retrieve the file paths of all sample events of one log class,
        the log class configuration"""
        dir_path = self.input_root_path / event_class_dir
        log_class_config = self._load_event_class_config(dir_path)

        files = dir_path.glob("*")
        file_paths = [dir_path / file_path for file_path in files if file_path.endswith(".jsonl")]
        return file_paths, log_class_config

    def _load_event_class_config(self, event_class_dir_path: Path) -> EventClassConfig:
        """Load the event class specific configuration"""
        config_path = event_class_dir_path / "config.yaml"
        with open(config_path, "r", encoding="utf8") as file:
            event_class_config = yaml.load(file)
        logger.debug("Following class config was loaded: %s", event_class_config)
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
                    events.append(f"{log_class_config.target_path},{event.strip()}")
                    # if len(events) == self.MAX_EVENTS_PER_FILE:
                    #     self._write_events_file(events)
