"""helper classes for logprep logging"""

import logging
import multiprocessing as mp
from logging.handlers import QueueListener
from socket import gethostname

logqueue = mp.Queue(-1)


class LogprepFormatter(logging.Formatter):
    """
    A custom formatter for logprep logging with additional attributes.

    The Formatter can be initialized with a format string which makes use of
    knowledge of the LogRecord attributes - e.g. the default value mentioned
    above makes use of the fact that the user's message and arguments are pre-
    formatted into a LogRecord's message attribute. The available attributes
    are listed in the
    `python documentation <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_ .
    Additionally, the formatter provides the following logprep specific attributes:

    .. table::

        +-----------------------+--------------------------------------------------+
        | attribute             | description                                      |
        +=======================+==================================================+
        | %(hostname)           | (Logprep specific) The hostname of the machine   |
        |                       | where the log was emitted                        |
        +-----------------------+--------------------------------------------------+

    """

    def format(self, record):
        record.hostname = gethostname()
        return super().format(record)


class LogprepMPQueueListener(QueueListener):
    """Logprep specific QueueListener that uses a multiprocessing instead of threading"""

    _process: mp.Process

    def start(self):
        self._process = mp.Process(target=self._monitor, daemon=True)
        self._process.start()

    def stop(self):
        self.enqueue_sentinel()
        if self._process and hasattr(self._process, "join"):
            self._process.join()
        self._process = None
