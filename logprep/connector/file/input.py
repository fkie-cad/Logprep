"""
FileInput
==========
A generic line input that returns the documents it was initialized with.
If a "document" is derived from BaseException, that exception will be thrown instead of
returning a document. The exception will be removed and subsequent calls may return documents or
throw other exceptions in the given order.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      myfileinput:
        type: file_input
        documents_path: path/to/a/document
        start: begin
        interval: 1
        watch_file: True
"""

import queue
import os
import zlib
import threading
from attrs import define, field, validators
from logprep.abc.input import Input


def threadsafe_function(func):
    """Decorator making sure that the decorated function is thread safe"""
    lock = threading.Lock()

    def new(*args, **kwargs):
        lock.acquire()
        try:
            func_wrapper = func(*args, **kwargs)
        except Exception as error:
            raise error
        finally:
            lock.release()
        return func_wrapper

    return new


class RepeatedTimerThread(threading.Thread):
    """This class is a minimal Thread Wrapper that runs a given function for a given time interval.
    To keep it simple, the interval isn't time-safe.
    It will wait for the given interval when one function execution finishes.

    :param interval: Defines how often the file is checked for changes
    :type interval: int
    :param function: Function that runs continuously with given interval
    :type function: function object
    :param stop_flag: Event-Flag that stops the thread if it's set
    :type stop_flag: threading.Event
    :param watch_file: this boolean flag decides whether the thread should run
        continuously or quit after one run
    :type watch_file: boolean
    :param args and kwargs: function specific arguments
    """

    def __init__(self, interval, function, stop_flag, watch_file, *args, **kwargs):
        super().__init__()
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.stopped = stop_flag
        self.watch_file = watch_file
        self.start()

    def run(self):
        while not self.stopped.wait(self.interval):
            self.function(*self.args, **self.kwargs)
            if not self.watch_file:
                self.stopped.set()


class FileWatcherDict:
    """This class provides a helper utility which creates a nested dict
    which holds information for every file that is watched in this instance.
    After a file is initiated the dict would look like:

        {"/var/log/logfile1": {"offset":123, "fingerprint": 0000001, "fingerprint_size":256}}

    The `offset` stores the current offset in the monitored file and the `fingerprint`
    stores the initial hash of a file that would change on log rotation.

    :param file_name: Name of the logfile that should be logged
    :type file_name: str
    """

    def __init__(self, file_name=""):
        self.dict = {}
        if file_name:
            self.add_file(file_name)

    def add_file(self, file_name):
        """adds initial structure for a new file"""
        self.dict[file_name] = {"offset": 0, "fingerprint": "", "fingerprint_size": ""}

    def add_offset(self, file_name, offset):
        """add new offset for file_name, add file as well if didn't exist"""
        if not self.get_fileinfo(file_name):
            self.add_file(file_name)
        self.dict[file_name]["offset"] = offset

    def add_fingerprint(self, file_name, fingerprint, fingerprint_size=256):
        """add new fingerprint for file_name, add file as well if didn't exist"""
        if not self.get_fileinfo(file_name):
            self.add_file(file_name)
        self.dict[file_name]["fingerprint"] = fingerprint
        self.dict[file_name]["fingerprint_size"] = fingerprint_size

    def add_fingerprint_size(self, file_name, fingerprint_size):
        """add new fingerprint_size for file_name, add file as well if didn't exist"""
        if not self.get_fileinfo(file_name):
            self.add_file(file_name)
        self.dict[file_name]["fingerprint_size"] = fingerprint_size

    def get_fileinfo(self, file_name):
        """get offset and fingerprint for given filename"""
        if self.dict.get(file_name):
            return self.dict[file_name]
        return ""

    def get_offset(self, file_name):
        """get offset for given filename"""
        if self.get_fileinfo(file_name):
            if self.dict[file_name].get("offset"):
                return self.dict[file_name]["offset"]
        return ""

    def get_fingerprint(self, file_name):
        """get fingerprint for given filename"""
        if self.get_fileinfo(file_name):
            if self.dict[file_name].get("fingerprint"):
                return self.dict[file_name]["fingerprint"]
        return ""

    def get_fingerprint_size(self, file_name):
        """get fingerprint size for given filename"""
        if self.get_fileinfo(file_name):
            if self.dict[file_name].get("fingerprint_size"):
                return self.dict[file_name]["fingerprint_size"]
        return ""

    def check_fingerprint(self, file_name, check_fingerprint):
        """compare a fingerprint with a existing fingerprint"""
        origin_fingerprint = self.get_fingerprint(file_name)
        if not origin_fingerprint:
            return True
        if origin_fingerprint == check_fingerprint:
            return True
        return False


class FileInput(Input):
    """FileInput Connector"""

    _messages: queue.Queue = queue.Queue()
    # this object is an nested dict with additional functions that helps to
    # keep track of file changes and current file offsets
    _fileinfo_util: object = FileWatcherDict()

    @define(kw_only=True)
    class Config(Input.Config):
        """FileInput connector specific configuration"""

        documents_path: str = field(validator=validators.instance_of(str))
        """A path to a file in generic raw format, which can be in any string based
        format. Needs to be parsed with normalizer or another processor"""

        @documents_path.validator
        def validate_documents_path(self, attribute, value):
            """ "Helper Function to validate the input values in the config file"""
            if not os.path.exists(value):
                raise ValueError(f"Config attribute {attribute} needs to point to a existing file")

        start: str = field(validator=[validators.instance_of(str), validators.in_(("begin","end"))], default="begin")
        """Defines the behaviour of the file monitor with the following options:
        ``begin``: starts to read from the beginning of a file
        ``end``: goes initially to the end of the file and waits for new content"""

        

        watch_file: str = field(validator=validators.instance_of(bool), default=True)
        """Defines the behaviour of the file monitor with the following options:
        ``True``: Read the file like defined in `start` param and monitor continuously
        for newly appended log lines or file changes
        ``False``: Read the file like defined in `start` param only once and exit afterwards"""

        interval: int = field(default=1, validator=validators.instance_of((int, float)))
        """Defines the refresh interval, how often the file is checked for changes"""

    def _calc_file_fingerprint(self, file_pointer, exist_fingerprint_size="") -> tuple:
        """This function creates a crc32 fingerprint of the first 256 bytes of a given file
        If the existing log file is less than 256 bytes, it will take what is there
        and return also the size"""
        if exist_fingerprint_size:
            fingerprint_length = exist_fingerprint_size
        else:
            file_size = self._get_file_size(self._config.documents_path)
            if 1 < file_size < 256:
                fingerprint_length = file_size
            else:
                fingerprint_length = 256
        fingerprint_bytes = str.encode(file_pointer.read(fingerprint_length))
        crc32 = zlib.crc32(fingerprint_bytes) % 2**32
        file_pointer.seek(0)
        return crc32, fingerprint_length

    def _get_file_size(self, file_name: str) -> int:
        """Get the full file size as byte based integer offset"""
        with open(file_name, encoding="utf-8") as file:
            file.readlines()
            initial_filepointer = file.tell()
        return initial_filepointer

    def _get_initial_file_offset(self, file_name: str) -> int:
        """Calculates the file_size for given logfile if it's configured to start
        at the end of a log file"""
        return self._get_file_size(file_name) if self._config.start == "end" else 0

    @threadsafe_function
    def _follow_file(self, file_name: str):
        """Put log_line as a dict to threadsafe message queue from given input file.
        Depending on configuration it will continuously monitor a given file for new
        appending log lines. Depending on configuration it will start to process the
        given file from the beginning or the end. Will create and continously check
        the file fingerprints to detect file changes that typically occur on log rotation."""

        with open(file_name, encoding="utf-8") as file:
            # creating the baseline fingerprint for the file
            if not self._fileinfo_util.get_fingerprint(file_name):
                baseline_crc32, baseline_fingerprint_size = self._calc_file_fingerprint(file)
                self._fileinfo_util.add_fingerprint(
                    file_name, baseline_crc32, baseline_fingerprint_size
                )

            baseline_fingerprint_size = self._fileinfo_util.get_fingerprint_size(file_name)
            check_crc32, _ = self._calc_file_fingerprint(file, baseline_fingerprint_size)
            if not self._fileinfo_util.check_fingerprint(file_name, check_crc32):
                # if the fingerprint in check_crc32 is not the same a non-appending
                # file change happened, create new baseline with potential new fingerprint_size
                new_check_crc32, new_fingerprint_size = self._calc_file_fingerprint(file)
                self._fileinfo_util.add_fingerprint(
                    file_name, new_check_crc32, new_fingerprint_size
                )
                self._fileinfo_util.add_offset(file_name, 0)

            while True:
                if self._fileinfo_util.get_offset(file_name):
                    # if the file offset already exists, continue from there
                    file.seek(self._fileinfo_util.get_offset(file_name))

                line = file.readline()
                # add new file offset after line of file was read
                self._fileinfo_util.add_offset(file_name, file.tell())
                if line != "":
                    if line.endswith("\n"):
                        message = self._line_to_dict(line)
                        if message:
                            self._messages.put(message)
                else:
                    break

    def _line_to_dict(self, input_line: str) -> dict:
        """Takes an input string and turns it into a dict without any parsing or formatting.
        Only thing it does additionally is stripping the new lines away."""
        input_line = input_line.rstrip("\n")
        if (isinstance(input_line, str)) and (len(input_line) > 0):
            return {"message": input_line}
        return ""

    def _get_event(self, timeout: float) -> tuple:
        """Returns the first message from the threadsafe queue"""
        try:
            message = self._messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message
        except queue.Empty:
            return None, None

    def setup(self):
        """Creates and starts the Thread that continously monitors the given logfile.
        Right now this input connector is only started in the first process.
        It needs the class attribute pipeline_index before running setup in Pipeline
        Initiation

        TODO (optional): when processing multiple files, map the threads
        equally-distributed to each process"""
        # create the event that will allow to kill the thread
        self.stop_flag = threading.Event()
        # we only start a thread in the first pipeline process
        # when processing multiple files they could be mapped to different processes
        if self.pipeline_index == 1:
            initial_pointer = self._get_initial_file_offset(self._config.documents_path)
            self._fileinfo_util.add_offset(self._config.documents_path, initial_pointer)
            self.rthread = RepeatedTimerThread(
                self._config.interval,
                self._follow_file,
                self.stop_flag,
                self._config.watch_file,
                file_name=self._config.documents_path,
            )

    def shut_down(self):
        """Raises the Stop Event Flag that will stop the thread that monitors the logfile

        TODO (optional): write the file offset and fingerprints to disk to continue later
        on on the same position"""
        self.stop_flag.set()
