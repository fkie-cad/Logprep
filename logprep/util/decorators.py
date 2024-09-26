"""Decorators to use with logprep"""

import errno
import os
import signal
from functools import wraps


def timeout(seconds=100, error_message=os.strerror(errno.ETIME)):
    """Calls a function with a defined timeout"""

    def decorator(func):
        def _handle_timeout(signum, frame):  # nosemgrep
            raise TimeoutError(error_message)

        @wraps(func)  # nosemgrep
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator
