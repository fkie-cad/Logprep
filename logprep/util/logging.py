"""Different helper-functions and -classes for support logging"""

# pragma: no cover

import time
import logging
import logging.handlers
import threading
from queue import Empty


# gratefully using implementation
# from https://medium.com/@augustomen/using-logging-asynchronously-c8e854de874c
class SingleThreadQueueListener(logging.handlers.QueueListener):
    """A subclass of QueueListener that uses a single thread for all queues.

    See https://github.com/python/cpython/blob/main/Lib/logging/handlers.py
    for the implementation of QueueListener.
    """

    monitor_thread = None
    listeners = []
    sleep_time = 0.1

    @classmethod
    def _start(cls):
        """Start a single thread, only if none is started."""
        if cls.monitor_thread is None or not cls.monitor_thread.is_alive():
            cls.monitor_thread = t = threading.Thread(
                target=cls._monitor_all, name="logging_monitor"
            )
            t.daemon = True
            t.start()
        return cls.monitor_thread

    @classmethod
    def _join(cls):
        """Waits for the thread to stop.
        Only call this after stopping all listeners.
        """
        if cls.monitor_thread is not None and cls.monitor_thread.is_alive():
            cls.monitor_thread.join()
        cls.monitor_thread = None

    @classmethod
    def _monitor_all(cls):
        """A monitor function for all the registered listeners.
        Does not block when obtaining messages from the queue to give all
        listeners a chance to get an item from the queue. That's why we
        must sleep at every cycle.

        If a sentinel is sent, the listener is unregistered.
        When all listeners are unregistered, the thread stops.
        """
        noop = None
        while cls.listeners:
            time.sleep(cls.sleep_time)  # does not block all threads
            for listener in cls.listeners:
                try:
                    # Gets all messages in this queue without blocking
                    task_done = getattr(listener.queue, "task_done", noop)
                    while True:
                        record = listener.dequeue(False)
                        if record is listener._sentinel:  # pylint: disable=protected-access
                            cls.listeners.remove(listener)
                        else:
                            listener.handle(record)
                        task_done()
                except Empty:
                    continue
                except TypeError:
                    continue

    def start(self):
        """Override default implementation.
        Register this listener and call class' _start() instead.
        """
        SingleThreadQueueListener.listeners.append(self)
        # Start if not already
        SingleThreadQueueListener._start()

    def stop(self):
        """Enqueues the sentinel but does not stop the thread."""
        self.enqueue_sentinel()
