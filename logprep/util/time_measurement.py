"""This module is used to measure the execution time of functions and add the results to events."""

from socket import gethostname
from time import time

from logprep.util.helper import camel_to_snake


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    TIME_MEASUREMENT_ENABLED = False
    APPEND_TO_EVENT = False
    HOSTNAME = gethostname()

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
                if TimeMeasurement.TIME_MEASUREMENT_ENABLED:
                    caller = args[0]
                    first_argument = args[1]
                    begin = time()
                    result = func(*args, **kwargs)
                    end = time()

                    processing_time = end - begin

                    if hasattr(caller, "metrics"):
                        if hasattr(caller.metrics, "update_mean_processing_time_per_event"):
                            caller.metrics.update_mean_processing_time_per_event(processing_time)

                    if TimeMeasurement.APPEND_TO_EVENT and isinstance(first_argument, dict):
                        add_processing_times_to_event(first_argument, processing_time, caller, name)
                    return result
                return func(*args, **kwargs)

            def add_processing_times_to_event(event, processing_time, caller, name):  # nosemgrep
                if not event.get("processing_times"):
                    event["processing_times"] = {}
                if name is None:
                    name = f"{camel_to_snake(caller.__class__.__name__)}"
                event["processing_times"][name] = float(f"{processing_time:.10f}")
                if "hostname" not in event["processing_times"].keys():
                    event["processing_times"]["hostname"] = TimeMeasurement.HOSTNAME

            return inner

        return inner_decorator
