"""
This module provides functionalities to load and handle files from a
specified directory for processing in logprep pipelines.
"""

import io
import logging
import shutil
from pathlib import Path
from typing import Generator, List

logger = logging.getLogger("Loader")


class FileLoader:
    """Handles file operations like reading files, shuffling, and cycling through them."""

    def __init__(self, directory: str | Path, **config) -> None:
        self.directory = Path(directory)
        self.event_count = config.get("events", 1)
        self.exit_requested = False

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
        for file in self.files:
            with open(file, "r", encoding="utf8", buffering=io.DEFAULT_BUFFER_SIZE) as current_file:
                while line := current_file.readline():
                    yield line
                    if self.exit_requested:
                        return

    def clean_up(self) -> None:
        """Deletes the temporary directory."""
        if self.directory.exists():
            shutil.rmtree(self.directory)

    def close(self) -> None:
        """Stops the thread."""
        self.exit_requested = True
        self.clean_up()
