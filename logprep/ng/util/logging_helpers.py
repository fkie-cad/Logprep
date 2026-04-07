"""helper classes for logprep logging"""

import asyncio
import threading

from logprep.util.logging import LogprepFormatter as NonNgLogprepFormatter
from logprep.util.logging import LogprepMPQueueListener as NonNgLogprepMPQueueListener


class LogprepFormatter(NonNgLogprepFormatter):
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
        | %(taskName)           | The name of the executing asyncio task.          |
        +-----------------------+--------------------------------------------------+

    """

    def format(self, record):
        # patch taskName for older python version (at least 3.11)
        try:
            record.taskName = asyncio.current_task().get_name()
        except Exception:  # pylint: disable=broad-exception-caught
            record.taskName = threading.current_thread().name
        return super().format(record)


class LogprepMPQueueListener(NonNgLogprepMPQueueListener):
    """Logprep specific QueueListener that uses a multiprocessing instead of threading"""
