"""helper classes for logprep logging"""

import logging
import logging.handlers
from socket import gethostname


class LogprepListener(logging.handlers.QueueListener):
    """custom QueueListener for logprep logging"""


class LogprepFormatter(logging.Formatter):
    """
    A custom formatter for logprep logging with additional attributes.

    The Formatter can be initialized with a format string which makes use of
    knowledge of the LogRecord attributes - e.g. the default value mentioned
    above makes use of the fact that the user's message and arguments are pre-
    formatted into a LogRecord's message attribute. Currently, the useful
    attributes in a LogRecord are described by:

    .. table::

        +-----------------------+--------------------------------------------------+
        | attribute             | description                                      |
        +=======================+==================================================+
        | %(name)s              | Name of the logger (logging channel)             |
        +-----------------------+--------------------------------------------------+
        | %(levelno)s           | Numeric logging level for the message            |
        +-----------------------+--------------------------------------------------+
        | %(levelname)s         | Text logging level for the message               |
        +-----------------------+--------------------------------------------------+
        | %(pathname)s          | Full pathname of the source file                 |
        +-----------------------+--------------------------------------------------+
        | %(filename)s          | Filename portion of pathname                     |
        +-----------------------+--------------------------------------------------+
        | %(module)s            | Module (name portion of filename)                |
        +-----------------------+--------------------------------------------------+
        | %(lineno)d            | Source line number where the logging call        |
        +-----------------------+--------------------------------------------------+
        | %(funcName)s          | Function name                                    |
        +-----------------------+--------------------------------------------------+
        | %(created)f           | Time when the LogRecord was created              |
        +-----------------------+--------------------------------------------------+
        | %(asctime)s           | Textual time when the LogRecord was created      |
        +-----------------------+--------------------------------------------------+
        | %(msecs)d             | Millisecond portion of the creation time         |
        +-----------------------+--------------------------------------------------+
        | %(relativeCreated)d   | Time in milliseconds when the LogRecord was      |
        |                       | created, relative to the time the logging module |
        |                       | was loaded                                       |
        +-----------------------+--------------------------------------------------+
        | %(thread)d            | Thread ID                                        |
        +-----------------------+--------------------------------------------------+
        | %(threadName)s        | Thread name                                      |
        +-----------------------+--------------------------------------------------+
        | %(process)d           | Process ID                                       |
        +-----------------------+--------------------------------------------------+
        | %(message)s           | The result of record.getMessage()                |
        +-----------------------+--------------------------------------------------+
        | %(hostname)           | (Logprep specific) The hostname of the machine   |
        |                       | where the log was emitted                        |
        +-----------------------+--------------------------------------------------+

    """

    def format(self, record):
        record.hostname = gethostname()
        return super().format(record)
