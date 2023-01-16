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

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.next_call = time.time()
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self.next_call += self.interval
            self._timer = threading.Timer(self.next_call - time.time(), self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


class FileInput(Input):
    """FileInput Connector"""

    _messages: queue.Queue = queue.Queue()
    
    @define(kw_only=True)
    class Config(Input.Config):
        """FileInput connector specific configuration"""

        documents_path: str
        """A path to a file in generic raw format, which can be in any string based format. Needs to be parsed with normalizer"""


    @property
    def _documents(self):
        return self._iterator
   

    def _follow_file(self, sleep_sec=1, exit_end=False): 
        """ Yield line from given input file and wait for arriving new lines.
        `sleep_sec` allows to wait for rereading the file buffer to decrease compute load
        `exit_end` allows deactivate tail behaviour and will exit on the last input line if activated

        TODO: Turn this from dirty while True to Timer triggered parallel thread or process"""
        with open(self._config.documents_path) as file:
            while True:
                line = file.readline()
                if line is not '':
                    if line.endswith("\n"):
                        self._messages.put(self._line_to_dict(line))
                        line = ''
                elif exit_end:
                    break
                elif sleep_sec:
                    time.sleep(sleep_sec)

    
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
        rt = RepeatedTimer(1,self._follow_file)
