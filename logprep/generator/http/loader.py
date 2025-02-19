import logging
import shutil
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Generator, List

from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE

logger = logging.getLogger("Loader")


class EventBuffer:
    """Handles the read and write operation into the buffer"""

    _message_backlog: Queue

    _sentinel = object()

    _thread: Thread

    def __init__(
        self, file_loader: "FileLoader", message_backlog_size: int = DEFAULT_MESSAGE_BACKLOG_SIZE
    ) -> None:
        self.file_loader = file_loader
        self._message_backlog = Queue(maxsize=message_backlog_size)
        self._thread = Thread(target=self.write)

    def __enter__(self) -> "EventBuffer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def write(self) -> None:
        """Reads lines from the file loader and puts them into the message backlog queue.
        This method blocks if queue is full.
        """
        for line in self.file_loader.read_lines():
            if self._message_backlog.full():
                logger.warning("Message backlog queue is full. Blocking until space is available.")
            self._message_backlog.put(line)

    def read_lines(self) -> Generator[str, None, None]:
        """Reads lines from the message backlog queue.

        Yields:
        -------
        str:
            A line from the message backlog queue.
        """
        while True:
            event = self._message_backlog.get()
            if event is self._sentinel:
                break
            yield event

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._message_backlog.put(self._sentinel)
        self._thread.join()


class FileLoader:
    """Handles file operations like reading files, shuffling, and cycling through them."""

    def __init__(self, directory: str | Path, **config) -> None:
        message_backlog_size = config.get("message_backlog_size", DEFAULT_MESSAGE_BACKLOG_SIZE)
        self._buffer = EventBuffer(message_backlog_size)
        self.directory = Path(directory)

    @property
    def files(self) -> List[str]:
        """Gets a list of valid files from the given directory."""
        if not self.directory.exists() or not self.directory.is_dir():
            raise FileNotFoundError(
                f"Directory '{self.directory}' does not exist or is not a directory."
            )

        files = self.directory.glob("*")
        if not files:
            raise FileNotFoundError(f"No files found in '{self.directory}'.")
        return files

    def write_backlog(self):
        """Reads lines and puts them into the message backlog queue."""
        for line in self.read_lines():
            self._buffer.write(line)

    def read_lines(self) -> Generator[str, None, None]:
        """Endless loop over files."""
        with self._buffer as buffer:
            yield from buffer.read_lines()

    def clean_up(self) -> None:
        """Deletes the temporary directory."""
        if self.directory.exists():
            shutil.rmtree(self.directory)
