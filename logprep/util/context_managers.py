"""Context managers to use with logprep"""

import logging
from contextlib import contextmanager

from logprep.util.logging import LogprepMPQueueListener, logqueue


@contextmanager
def logqueue_listener(logger_name: str):
    """Run logqueue listener for specified logger name."""
    console_logger = logging.getLogger(logger_name)
    if console_logger.handlers:
        listener = LogprepMPQueueListener(logqueue, console_logger.handlers[0])
        listener.start()
        yield
        listener.stop()
    else:
        yield
