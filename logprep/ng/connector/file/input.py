"""
FileInput
==========
A generic line input that returns the documents it was initialized with.
If a "document" is derived from Exception, that exception will be thrown instead of
returning a document. The exception will be removed and subsequent calls may return documents or
throw other exceptions in the given order.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      myfileinput:
        type: file_input
        logfile_path: path/to/a/document
        start: begin
        interval: 1
        watch_file: True
"""

import queue
import threading
import typing
import zlib
from typing import TextIO

from attrs import define, field, validators

from logprep.abc.input import FatalInputError
from logprep.connector.file.input import (
    FileWatcherUtil,
    RepeatedTimerThread,
    runtime_file_exceptions,
    threadsafe_wrapper,
)
from logprep.ng.abc.input import Input
from logprep.util.validators import file_validator


class FileInput(Input):
    """FileInput Connector"""

    _messages: queue.Queue = queue.Queue()
    _fileinfo_util: FileWatcherUtil = FileWatcherUtil()
    rthread: threading.Thread | None = None

    @define(kw_only=True)
    class Config(Input.Config):
        """FileInput connector specific configuration"""

        logfile_path: str = field(validator=file_validator)
        """A path to a file in generic raw format, which can be in any string based
        format. Needs to be parsed with dissector or another processor"""

        start: str = field(
            validator=(validators.instance_of(str), validators.in_(("begin", "end"))),
            default="begin",
        )
        """Defines the behaviour of the file monitor with the following options:
        - ``begin``: starts to read from the beginning of a file
        - ``end``: goes initially to the end of the file and waits for new content"""

        watch_file: bool = field(validator=validators.instance_of(bool), default=True)
        """Defines the behaviour of the file monitor with the following options:
        - ``True``: Read the file like defined in `start` param and monitor continuously
        for newly appended log lines or file changes
        - ``False``: Read the file like defined in `start` param only once and exit afterwards"""

        interval: int = field(default=1, validator=validators.instance_of((int, float)))
        """Defines the refresh interval, how often the file is checked for changes"""

    def __init__(self, name: str, configuration: "FileInput.Config") -> None:
        super().__init__(name, configuration)
        self.stop_flag = threading.Event()

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(FileInput.Config, self._config)

    def _calc_file_fingerprint(
        self, file_pointer: TextIO, fingerprint_length: int | None = None
    ) -> tuple:
        """This function creates a crc32 fingerprint of the first 256 bytes of a given file
        If the existing log file is less than 256 bytes, it will take what is there
        and return also the size"""
        if not fingerprint_length:
            file_size: int = self._get_file_size(self.config.logfile_path)
            if 1 < file_size < 256:
                fingerprint_length = file_size
            else:
                fingerprint_length = 256
        fingerprint_bytes = str.encode(file_pointer.read(fingerprint_length))
        crc32 = zlib.crc32(fingerprint_bytes) % 2**32
        file_pointer.seek(0)
        return crc32, fingerprint_length

    @runtime_file_exceptions
    def _get_file_size(self, file_name: str) -> int:
        """Get the full file size as byte based integer offset"""
        with open(file_name, encoding="utf-8") as file:
            file.readlines()
            initial_filepointer: int = file.tell()
        return initial_filepointer

    def _get_initial_file_offset(self, file_name: str) -> int:
        """Calculates the file_size for given logfile if it's configured to start
        at the end of a log file"""
        return self._get_file_size(file_name) if self.config.start == "end" else 0

    def _follow_file(self, file_name: str, file: TextIO) -> None:
        """Will go through monitored file from offset to end of file"""
        file_not_ended = False
        while not file_not_ended:
            if self._fileinfo_util.get_offset(file_name):
                file.seek(self._fileinfo_util.get_offset(file_name))
            line = file.readline()
            self._fileinfo_util.add_offset(file_name, file.tell())
            if line != "":
                if line.endswith("\n"):
                    message: dict = self._line_to_dict(line)
                    if message:
                        self._messages.put(message)
            else:
                file_not_ended = True

    def _calc_and_update_fingerprint(self, file_name: str, file: TextIO) -> None:
        crc32, fingerprint_size = self._calc_file_fingerprint(file)
        self._fileinfo_util.add_fingerprint(file_name, crc32, fingerprint_size)

    def _calc_and_check_fingerprint(self, file_name: str, file: TextIO) -> bool:
        baseline_fingerprint_size: int = self._fileinfo_util.get_fingerprint_size(file_name)
        crc32, _ = self._calc_file_fingerprint(file, baseline_fingerprint_size)
        if self._fileinfo_util.has_fingerprint_changed(file_name, crc32):
            return True
        return False

    @threadsafe_wrapper
    @runtime_file_exceptions
    def _file_input_handler(self, file_name: str) -> None:
        """Put log_line as a dict to threadsafe message queue from given input file.
        Depending on configuration it will continuously monitor a given file for new
        appending log lines. Depending on configuration it will start to process the
        given file from the beginning or the end. Will create and continuously check
        the file fingerprints to detect file changes that typically occur on log rotation."""
        with open(file_name, encoding="utf-8") as file:
            if not self._fileinfo_util.get_fingerprint(file_name):
                self._calc_and_update_fingerprint(file_name, file)
            if self._calc_and_check_fingerprint(file_name, file):
                self._calc_and_update_fingerprint(file_name, file)
                self._fileinfo_util.add_offset(file_name, 0)
            self._follow_file(file_name, file)

    def _line_to_dict(self, input_line: str) -> dict:
        """Takes an input string and turns it into a dict without any parsing or formatting.
        Only thing it does additionally is stripping the new lines away."""
        input_line = input_line.rstrip("\n")
        if len(input_line) > 0:
            return {"message": input_line}
        return {}

    def _get_event(self, timeout: float) -> tuple:
        """Returns the first message from the threadsafe queue"""
        try:
            message: dict = self._messages.get(timeout=timeout)
            raw_message: bytes = str(message).encode("utf8")
            return message, raw_message, None
        except queue.Empty:
            return None, None, None

    def setup(self) -> None:
        """Creates and starts the Thread that continuously monitors the given logfile.
        Right now this input connector is only started in the first process.
        It needs the class attribute pipeline_index before running setup in Pipeline
        Initiation"""
        super().setup()
        if not hasattr(self, "pipeline_index"):
            raise FatalInputError(
                self, "Necessary instance attribute `pipeline_index` could not be found."  # type: ignore
            )
        if self.pipeline_index == 1:
            initial_file_pointer: int = self._get_initial_file_offset(self.config.logfile_path)
            self._fileinfo_util.add_offset(self.config.logfile_path, initial_file_pointer)
            self.rthread = RepeatedTimerThread(
                self.config.interval,
                self._file_input_handler,
                self.stop_flag,
                self.config.watch_file,
                file_name=self.config.logfile_path,
            )

    def _shut_down(self) -> None:
        """Raises the Stop Event Flag that will stop the thread that monitors the logfile"""
        self.stop_flag.set()
        return super()._shut_down()
