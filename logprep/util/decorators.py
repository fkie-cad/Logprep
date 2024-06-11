"""Decorators to use with logprep"""

import errno
import os
import random
import signal
import time
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


def retry_throttle(on_error, retry_fail_error, retries=5):
    """
    Execute function multiple times with raising delay inbetween

    If the error `on_error` occurs this function will sleep for a certain delay. If all
    retries are exceeded the error `retry_fail_error` will be raised.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay_seconds = 1
            for _ in range(retries):
                try:
                    result = func(*args, **kwargs)
                except on_error:  # sleep on error
                    time.sleep(delay_seconds)
                    delay_seconds += random.randint(500, 1000) / 1000
                else:  # exit retry mechanism on success
                    break
            else:  # throw retry_fail_error of all retries where unsuccessful
                raise retry_fail_error(args[0], "All retries failed")
            return result

        return wrapper

    return decorator
