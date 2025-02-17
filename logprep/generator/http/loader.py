import itertools
import logging
import multiprocessing
import os
import random
import shutil
import tempfile
from functools import cached_property
from operator import itemgetter
from pathlib import Path
from threading import Thread
from typing import Any, Generator, List, Tuple

import msgspec

from logprep.framework.pipeline_manager import ThrottlingQueue
from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE

logger = logging.getLogger("Loader")


class EventBuffer:
    """Handles the read and write operation into the buffer"""

    _message_backlog: ThrottlingQueue

    _sentinel = object()

    write_thread: Thread

    def __init__(
        self, file_loader: "FileLoader", message_backlog_size: int = DEFAULT_MESSAGE_BACKLOG_SIZE
    ) -> None:
        self.file_loader = file_loader
        ctx = multiprocessing.get_context()
        self._message_backlog = ThrottlingQueue(ctx, maxsize=message_backlog_size)

    def write(self) -> None:
        """Reads lines from the file loader and puts them into the message backlog queue.
        This method blocks if queue is full.
        """

        for line in self.file_loader.read_lines():
            if self._message_backlog.full():
                logger.warning("Message backlog queue is full. Blocking until space is available.")
            self._message_backlog.put(line)

    def read(self) -> Generator[str, None, None]:
        """Reads lines from the message backlog queue.

        Yields:
        -------
        str:
            A line from the message backlog queue.
        """
        while True:
            event = self._message_backlog.get()
            if (
                event is self._sentinel
            ):  # Todo: Returned sentinel object is not equal to the class sentinel
                break
            yield event

    def run(self) -> None:
        self.write_thread = Thread(target=self.write)
        self.write_thread.start()
        self.write_thread.join()

    def stop(self) -> None:
        self._message_backlog.put(self._sentinel)


class FileLoader:
    """Handles file operations like reading files, shuffling, and cycling through them."""

    def __init__(self, directory: str, **kwargs) -> None:
        self.directory = Path(directory)
        self.shuffle = kwargs.get("shuffle", False)
        self.files = self._get_files()

    def _get_files(self) -> List[str]:
        """Gets a list of valid files from the given directory."""
        if not os.path.exists(self.directory) or not os.path.isdir(self.directory):
            raise FileNotFoundError(
                f"Directory '{self.directory}' does not exist or is not a directory."
            )

        files = [os.path.join(self.directory, file) for file in os.listdir(self.directory)]
        if not files:
            raise ValueError(f"No files found in '{self.directory}'.")

        if self.shuffle:
            random.shuffle(files)
        return files

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
