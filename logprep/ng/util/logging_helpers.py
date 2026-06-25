"""helper classes for logprep logging"""

import asyncio
import logging
import queue
from collections.abc import Iterator
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener

from logprep.util.logging import LogprepFormatter as NonNgLogprepFormatter


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
        if not hasattr(record, "task_name"):
            record.task_name = None
        return super().format(record)


@contextmanager
def inject_task_names_in_log_records() -> Iterator[None]:
    """
    Inject the current task name in emitted log records.
    """

    base_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = base_factory(*args, **kwargs)

        task = asyncio.current_task()
        record.task_name = task.get_name() if task is not None else None

        return record

    logging.setLogRecordFactory(factory)

    yield

    logging.setLogRecordFactory(base_factory)


@contextmanager
def decouple_logging_via_queue(handler_name="console") -> Iterator[None]:
    """
    Decouple the root logger from the handler by injecting a queue
    and a dedicated listener thread which indirectly calls the handler.
    """

    root = logging.getLogger()

    try:
        console_handler = next(h for h in root.handlers if h.name == handler_name)
    except StopIteration as exc:
        raise RuntimeError(f"missing required log handler {handler_name}") from exc

    # TODO implement metric for dropped logs, make maxsize configurable
    log_queue: queue.Queue = queue.Queue(maxsize=10000)
    queue_handler = QueueHandler(log_queue)

    root.removeHandler(console_handler)
    root.addHandler(queue_handler)

    listener = QueueListener(
        log_queue,
        console_handler,
        respect_handler_level=True,
    )
    listener.start()

    try:
        yield
    finally:
        listener.stop()

    root.addHandler(console_handler)
    root.removeHandler(queue_handler)
