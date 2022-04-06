"""This module is used to measure the execution time of functions and add the results to events."""

from time import time
from socket import gethostname


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    TIME_MEASUREMENT_ENABLED = False
    APPEND_TO_EVENT = False
    HOSTNAME = gethostname()

    @staticmethod
    def measure_time(name: str):
        """Decorate function to measure execution time for function and add results to event.

        Parameters
        ----------
        name : str
            Name to write processing times to in event.

        """

        def inner_decorator(func):
            def inner(*args, **kwargs):
                if TimeMeasurement.TIME_MEASUREMENT_ENABLED:
                    caller = args[0]
                    event = args[1]
                    begin = time()
                    result = func(*args, **kwargs)
                    end = time()

                    processing_time = end - begin

                    if caller.__module__.endswith("processor"):
                        caller.ps.update_average_processing_time(processing_time)

                    if TimeMeasurement.APPEND_TO_EVENT:
                        add_processing_times_to_event(event, processing_time)
                    return result
                return func(*args, **kwargs)

            def add_processing_times_to_event(event, processing_time):
                if not event.get("processing_times"):
                    event["processing_times"] = dict()
                event["processing_times"][name] = float(f"{processing_time:.10f}")
                if "hostname" not in event["processing_times"].keys():
                    event["processing_times"]["hostname"] = TimeMeasurement.HOSTNAME

            return inner

        return inner_decorator
