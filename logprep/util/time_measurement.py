"""This module is used to measure the execution time of functions and add the results to events."""


import time


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    @staticmethod
    def measure_time(metric_name: str = "processing_time_per_event"):
        """Decorate function to measure execution time for function and add results to event."""

        def inner_decorator(func):
            def inner(*args, **kwargs):  # nosemgrep
                begin = time.time()
                result = func(*args, **kwargs)
                end = time.time()
                processing_time = end - begin
                caller = args[0]
                if func.__name__ in ("_process_rule_tree", "_process_rule"):
                    caller = args[-1]
                metric = getattr(caller.metrics, metric_name)
                metric += processing_time
                return result

            return inner

        return inner_decorator
