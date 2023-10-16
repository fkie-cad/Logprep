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
                caller = args[0]
                first_argument = args[1]
                second_argument = args[2] if len(args) > 2 else None
                begin = time()
                result = func(*args, **kwargs)
                end = time()

                processing_time = end - begin
                if name in ("Rule processing",):
                    caller = first_argument
                    caller.metrics.processing_time_per_event += processing_time
                if name in ("RuleTree processing",):
                    caller = second_argument
                    caller.metrics.processing_time_per_event += processing_time
                return result

            return inner

        return inner_decorator
