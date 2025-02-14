import itertools
import os
import random
import shutil
import tempfile
from functools import cached_property
from operator import itemgetter
from pathlib import Path
from typing import Any, Generator, List, Tuple

import msgspec


class FileLoader:
    """Handles file operations like reading files, shuffling, and cycling through them."""

    def __init__(self, directory: str):
        self.directory = directory

    def read_lines(self, input_files) -> Generator[str, None, None]:
        """Reads files line by line, either once or infinitely."""
        for event_files in input_files:
            with open(event_files, "r", encoding="utf8") as file:
                yield from file

    def infinite_read_lines(self, input_files) -> Generator[str, None, None]:
        """Endless loop over files."""
        for event_files in itertools.cycle(input_files):
            with open(event_files, "r", encoding="utf8") as file:
                yield from file

    def clean_up(self):
        """Deletes the temporary directory."""
        if os.path.exists(self.directory) and os.path.isdir(self.directory):
            shutil.rmtree(self.directory)


class EventProcessor:
    """Processes event lines, applies decoding & manipulation, and prepares for request sending."""

    @cached_property
    def _decoder(self):
        return msgspec.json.Decoder()

    def __init__(self):
        self.log_class_manipulator_mapping = {}

    def process_event_line(self, line: str) -> Tuple[str, Any]:
        """Parses an event line and applies manipulation."""
        class_target, event = line.split(",", maxsplit=1)
        parsed_event = self._decoder.decode(event)
        manipulator = self.log_class_manipulator_mapping.get(class_target)
        manipulated_event = manipulator.manipulate([parsed_event])[0]
        return class_target, manipulated_event

    def create_request_data(
        self, event_batch: List[Tuple[str, Any]]
    ) -> Generator[Tuple[str, List[Any]], None, None]:
        """Reformats events into structured payloads."""
        sorted_batch = sorted(event_batch, key=lambda x: x[0])
        for target_path, events in itertools.groupby(sorted_batch, key=lambda x: x[0]):
            yield target_path, list(map(itemgetter(1), events))


class EventLoader:
    """
    Loads events from files and processes them in batches.
    """

    @cached_property
    def _temp_dir(self):
        return Path(tempfile.mkdtemp(prefix="logprep_"))

    def __init__(self, config):
        self.event_limit = config.get("events")
        self.batch_size = config.get("batch_size")
        self.shuffle = config.get("shuffle", False)

        self.file_loader = FileLoader(config.get("input_root_path"))
        self.event_processor = EventProcessor()
        self.events_sent = 0

    def _get_files(self) -> List[str]:
        files = [os.path.join(self._temp_dir, file) for file in os.listdir(self._temp_dir)]
        if self.shuffle:
            random.shuffle(files)
        return files

    def load(self) -> Generator[List, None, None]:
        """Generates processed event batches."""
        files = self._get_files()
        file_reader = (
            self.file_loader.read_lines(files)
            if self.event_limit is None
            else self.file_loader.infinite_read_lines(files)
        )
        yield from self._process_events(file_reader)

    def _process_events(
        self, file_reader: Generator[str, None, None]
    ) -> Generator[List, None, None]:
        events = []
        for line in file_reader:
            if self.event_limit and self.events_sent >= self.event_limit:
                return
            events.append(self.event_processor.process_event_line(line))
            if len(events) >= self.batch_size:
                yield from self.event_processor.create_request_data(events)
                self.events_sent += len(events)
                events.clear()
