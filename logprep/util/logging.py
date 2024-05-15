"""helper classes for logprep logging"""

import logging
import multiprocessing as mp
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
