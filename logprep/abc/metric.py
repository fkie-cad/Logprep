"""This module tracks, calculates, exposes and resets logprep metrics"""
import functools
import operator
from attr import define


@define(kw_only=True)
class Metric:
    """Base Metric class to track and expose statistics about logprep"""
    _labels: dict
    _prefix: str = "logprep_"
    _do_not_expose = ["expose", "reset_statistics"]

    def expose(self):
        """Iterates and collects all metrics and linked metrics in a common list."""
        exp = []
        for attribute in dir(self):
            if not attribute.startswith("_") and attribute not in self._do_not_expose:
                attribute_value = self.__getattribute__(attribute)
                if isinstance(attribute_value, list):
                    child_metrics = [value.expose() for value in attribute_value]
                    exp.extend(functools.reduce(operator.iconcat, child_metrics, []))
                else:
                    labels = [":".join(item) for item in self._labels.items()]
                    labels = ','.join(labels)
                    metric_key = f"{self._prefix}{attribute}"
                    exp.append(f"{metric_key} {labels} {attribute_value}")
        return exp

    def reset_statistics(self):
        """Resets the statistics of self and children to 0"""
        for attribute in dir(self):
            if not attribute.startswith("_"):
                attribute_value = self.__getattribute__(attribute)
                if isinstance(attribute_value, list):
                    attribute_value = [child.reset_statistics() for child in attribute_value]
                if isinstance(attribute_value, int):
                    attribute_value = 0
                if isinstance(attribute_value, float):
                    attribute_value = 0.0
                self.__setattr__(attribute, attribute_value)
        return self


def calculate_new_average(current_average, next_sample, sample_counter):
    """Calculate a new average by combining a new sample with a sample counter"""
    average_multiple = current_average * sample_counter
    extended_average_multiple = average_multiple + next_sample
    sample_counter += 1
    new_average = extended_average_multiple / sample_counter
    return new_average
