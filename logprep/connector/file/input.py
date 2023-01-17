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
"""

from attrs import define
from logprep.abc.input import Input
import threading 
import queue
import zlib


def threadsafe_function(fn):
    """decorator making sure that the decorated function is thread safe"""
    lock = threading.Lock()
    def new(*args, **kwargs):
        lock.acquire()
        try:
            r = fn(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            lock.release()
        return r
    return new


class RepeatedTimerThread(threading.Thread):
    def __init__(self, interval, input_object, stop_flag, *args, **kwargs):
        super(RepeatedTimerThread,self).__init__()
        self._timer = None
        self.interval = interval
        self.input_object = input_object
        self.args = args
        self.kwargs = kwargs
        self.stopped = stop_flag
        self.start()


    def run(self):
        while not self.stopped.wait(self.interval):
            self.input_object._follow_file(*self.args, **self.kwargs)


class FileWatcherDict(object):
    def __init__(self, file_name=""):
        self.d = {}
        if file_name:
            self.add_file(file_name)


    def add_file(self, file_name):
        self.d[file_name] = {"offset":0,"fingerprint":""}
    
    
    def add_offset(self, file_name, offset):
        if not self.get_fileinfo(file_name):
            self.add_file(file_name)
        self.d[file_name]["offset"] = offset


    def add_fingerprint(self, file_name, fingerprint):
        if not self.get_fileinfo(file_name):
            self.add_file(file_name)
        self.d[file_name]["fingerprint"] = fingerprint


    def get_fileinfo(self, file_name):
        if self.d.get(file_name):
            return self.d[file_name]
        else:
            return ""


    def get_offset(self, file_name):
        if self.get_fileinfo(file_name):
            if self.d[file_name].get("offset"):
                return self.d[file_name]["offset"]
            else:
                return ""
        else:
            return ""


    def get_fingerprint(self, file_name):
        if self.get_fileinfo(file_name): 
            if self.d[file_name].get("fingerprint"):
                return self.d[file_name]["fingerprint"]
            else:
                return ""
        else:
            return ""


    def check_fingerprint(self, file_name, check_fingerprint):
        origin_fingerprint = self.get_fingerprint(file_name)
        if not origin_fingerprint:
            return True

        if origin_fingerprint == check_fingerprint:
            return True
        else:
            return False


class FileInput(Input):
    """FileInput Connector"""

    _messages: queue.Queue = queue.Queue()
    _fileinfo_util: object = FileWatcherDict()

    @define(kw_only=True)
    class Config(Input.Config):
        """FileInput connector specific configuration"""

        documents_path: str
        """A path to a file in generic raw format, which can be in any string based format. Needs to be parsed with normalizer"""


    def _calc_file_fingerprint(self, fp) -> int:
        """
        This function creates a crc32 fingerprint of the first 256 bytes of a given file
        """
        first_256_bytes = str.encode(fp.read(256))
        crc32 = zlib.crc32(first_256_bytes)% 2**32
        fp.seek(0)
        return crc32


    @threadsafe_function
    def _follow_file(self, file_name: str): 
        """ 
        Put line as a dict to threadsafe message queue from given input file and wait for arriving new lines.
        Will create and continously check the file fingerprints to detect file changes that occur on log rotation.
        """
            
        with open(file_name) as file:
            # creating the baseline fingerprint for the file
            if not self._fileinfo_util.get_fingerprint(file_name):
               self._fileinfo_util.add_fingerprint(file_name, self._calc_file_fingerprint(file))
            
            check_crc32 = self._calc_file_fingerprint(file)
            if not self._fileinfo_util.check_fingerprint(file_name, check_crc32):
                # if the fingerprint in check_crc32 is not the same a non-appending file change happened
                self._fileinfo_util.add_fingerprint(file_name, check_crc32)
                self._fileinfo_util.add_offset(file_name, 0)

            while True:
                if self._fileinfo_util.get_offset(file_name):
                    file.seek(self._fileinfo_util.get_offset(file_name))
                line = file.readline()
                self._fileinfo_util.add_offset(file_name, file.tell())
                if line is not '':
                    if line.endswith("\n"):
                        self._messages.put(self._line_to_dict(line))
                else:
                    break

    
    def _line_to_dict(self, input_line: str) -> dict:
        if type(input_line) == str:
            dict_line = {"line":input_line.rstrip("\n")}
        else:
            dict_line = {"line":""}
        return dict_line


    def _get_event(self, timeout: float) -> tuple:
        """returns the first message from the queue"""
        try:
            message = self._messages.get(timeout=timeout)
            raw_message = str(message).encode("utf8")
            return message, raw_message
        except queue.Empty:
            return None, None

    
    def setup(self):
        """
        Creates and starts the Thread that continously monitors the given logfile.

        TODO: this function is executed for every process in process_count, 
        which leads to multiple Thread instances for the same file -> not desired
        The Thread needs to run as a singleton per document path for spawning it 
        over multiple processes
        """
        self.stop_flag = threading.Event()
        self.rt = RepeatedTimerThread(  2,
                                        self, 
                                        self.stop_flag,
                                        file_name=self._config.documents_path)


    def shut_down(self):
        """
        Raises the Stop Event Flag that will stop the thread that monitors the logfile

        TODO (optional): write the file offset and fingerprints to disk to continue later on on the same position
        """
        self.stop_flag.set()
