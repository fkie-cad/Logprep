import logging
import shutil
import threading
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Generator, List

from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE

logger = logging.getLogger("Loader")


class EventBuffer:
    """Handles the read and write operation into the buffer"""

    _message_backlog: Queue

    _sentinel = object()

    _thread: threading.Thread

    def __init__(
        self, file_loader: "FileLoader", message_backlog_size: int = DEFAULT_MESSAGE_BACKLOG_SIZE
    ) -> None:
        self.file_loader = file_loader
        self._message_backlog = Queue(maxsize=message_backlog_size)
        self._thread = threading.Thread(target=self.write)
        self.exit_requested = False

    def write(self) -> None:
        """Reads lines from the file loader and puts them into the message backlog queue.
        This method blocks if queue is full.
        """
        for file in self.file_loader.files:
            if self.exit_requested:
                break
            with open(file, "r", encoding="utf8") as current_file:
                while line := current_file.readline():
                    succeeded = False
                    while not succeeded:
                        try:
                            self._message_backlog.put(line.strip(), timeout=1)
                            succeeded = True
                        except Full:
                            logger.warning("Message backlog queue is full. ")
        self._message_backlog.put(self._sentinel)

    def read_lines(self) -> Generator[str, None, None]:
        """Reads lines from the message backlog queue.

        Yields:
        -------
        str:
            A line from the message backlog queue.
        """
        while True:
            try:
                event = self._message_backlog.get(timeout=1)
            except Empty:
                continue
            if event is self._sentinel:
                break
            yield event

    def start(self) -> None:
        """Starts the thread."""
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self) -> None:
        """Stops the thread."""
        self._message_backlog.put(self._sentinel)
        self.exit_requested = True
        self._thread.join()


class FileLoader:
    """Handles file operations like reading files, shuffling, and cycling through them."""

    def __init__(self, directory: str | Path, **config) -> None:
        message_backlog_size = config.get("message_backlog_size", DEFAULT_MESSAGE_BACKLOG_SIZE)
        self._buffer = EventBuffer(self, message_backlog_size)
        self.directory = Path(directory)
        self.event_count = config.get("events", 1)

    @property
    def files(self) -> List[Path]:
        """Gets a list of valid files from the given directory."""
        if not self.directory.exists() or not self.directory.is_dir():
            raise FileNotFoundError(
                f"Directory '{self.directory}' does not exist or is not a directory."
            )

        files = self.directory.glob("*")
        if not files:
            raise FileNotFoundError(f"No files found in '{self.directory}'.")
        return files

    def read_lines(self) -> Generator[str, None, None]:
        """Endless loop over files."""
        yield from self._buffer.read_lines()

    def clean_up(self) -> None:
        """Deletes the temporary directory."""
        if self.directory.exists():
            shutil.rmtree(self.directory)

    def start(self) -> None:
        """Starts the thread."""
        self._buffer.start()

    def close(self) -> None:
        """Stops the thread."""
        self._buffer.stop()
        while self._buffer._thread.is_alive():
            logger.info("Waiting for buffer thread to finish")
        self.clean_up()
