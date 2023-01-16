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
import time
import threading 
import time
import queue
from multiprocessing import Process, Event, Queue


class RepeatedTimerThread(object):
    def __init__(self, interval, function, event,*args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.stopped = event
        self.next_call = time.time()
        self.start()


    def _run(self):
        if not self.stopped.is_set():
            self.is_running = False
            self.start()
            self.function(*self.args, **self.kwargs)
        else:
            self.stop()

    def start(self):
        if (not self.is_running) and (not self.stopped.is_set()):
            self.next_call += self.interval
            self._timer = threading.Timer(self.next_call - time.time(), self._run)
            self._timer.start()
            self.is_running = True
        else:
            self.stop()

    def stop(self):
        self.is_running = False
        self._timer.cancel()



class FileInput(Input):
    """FileInput Connector"""

    _messages: queue.Queue = queue.Queue()
    _fileinfo_dict: dict = {}

    @define(kw_only=True)
    class Config(Input.Config):
        """FileInput connector specific configuration"""

        documents_path: str
        """A path to a file in generic raw format, which can be in any string based format. Needs to be parsed with normalizer"""


    @property
    def _documents(self):
        return self._iterator
   

    def _follow_file(self, file_name): 
        """ Yield line from given input file and wait for arriving new lines.

        TODO: Turn this from dirty while True to Timer triggered parallel thread or process"""
        with open(file_name) as file:
            while True:
                if self._fileinfo_dict.get(file_name):
                    file.seek(self._fileinfo_dict[file_name])

                line = file.readline()
                self._fileinfo_dict[file_name] = file.tell()
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
        super().setup()
        self.stop_flag = Event()
        self.rt = RepeatedTimerThread(1,self._follow_file, self.stop_flag, file_name=self._config.documents_path)


    def shut_down(self):
        self.stop_flag.set()
