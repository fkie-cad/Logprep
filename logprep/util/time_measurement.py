"""This module is used to measure the execution time of functions and add the results to events."""

from time import time
from socket import gethostname


class TimeMeasurement:
    """Measures the execution time of functions and adds the results to events via a decorator."""

    TIME_MEASUREMENT_ENABLED = False
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
                    event = args[1]
                    begin = time()
                    result = func(*args, **kwargs)
                    end = time()

                    if not event.get("processing_times"):
                        event["processing_times"] = dict()
                    event["processing_times"][name] = float("{:.10f}".format(end - begin))

                    if "hostname" not in event["processing_times"].keys():
                        event["processing_times"]["hostname"] = TimeMeasurement.HOSTNAME
                    return result
                return func(*args, **kwargs)

            return inner

        return inner_decorator
