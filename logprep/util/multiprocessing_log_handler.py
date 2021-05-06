"""This module is used to handle logging with multi processing."""

from logging import Handler, LogRecord
from multiprocessing import Queue


class MultiprocessingLogHandler(Handler):
    """Log handles with multi processing capabilities."""

    def __init__(self, log_level: int):
        self._queue = Queue()
        super().__init__(log_level)

    def handle(self, record: LogRecord):
        self._queue.put(record, block=True)

    def get(self, timeout: float) -> LogRecord:
        """Get log event from multi processing queue.

        Parameters
        ----------
        timeout : float
            Time after which the blocking queue should timeout.

        """
        if timeout <= 0.0:
            return self._queue.get(block=False)
        return self._queue.get(block=True, timeout=timeout)
