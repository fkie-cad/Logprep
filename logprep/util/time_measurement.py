"""This module is used to measure the execution time of functions and add the results to events."""


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    @staticmethod
    def measure_time():
        """Decorate function to measure execution time for function and add results to event."""

        def inner_decorator(func):
            def inner(*args, **kwargs):  # nosemgrep
                caller = args[0]
                if func.__name__ in ("_process_rule_tree", "_process_rule"):
                    caller = args[-1]
                with caller.metrics.processing_time_per_event.time():
                    result = func(*args, **kwargs)
                return result

            return inner

        return inner_decorator
