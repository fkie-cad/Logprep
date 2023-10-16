"""This module is used to measure the execution time of functions and add the results to events."""

from time import time


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    @staticmethod
    def measure_time(name: str = None):
        """Decorate function to measure execution time for function and add results to event.

        Parameters
        ----------
        name : str
            Name to write processing times to in event.
        """

        def inner_decorator(func):
            def inner(*args, **kwargs):  # nosemgrep
                begin = time()
                result = func(*args, **kwargs)
                end = time()
                processing_time = end - begin
                caller = args[0]
                if func.__name__ in ("_process_rule_tree", "_process_rule"):
                    caller = args[-1]
                caller.metrics.processing_time_per_event += processing_time
                return result

            return inner

        return inner_decorator
