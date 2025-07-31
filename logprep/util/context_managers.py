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
        try:
            yield
        finally:
            listener.stop()
    else:
        yield


@contextmanager
def disable_loggers():
    """Temporarily disable enabled loggers."""
    loggers = logging.root.manager.loggerDict.values()
    defined_loggers = [logger for logger in loggers if isinstance(logger, logging.Logger)]
    enabled_loggers = [logger for logger in defined_loggers if logger.disabled is False]
    for logger in enabled_loggers:
        logger.disabled = True
    try:
        yield
    finally:
        for logger in enabled_loggers:
            logger.disabled = False
