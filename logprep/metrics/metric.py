"""This module tracks, calculates, exposes and resets logprep metrics"""
from collections import namedtuple

from attr import define, asdict

MetricTargets = namedtuple("MetricTargets", "file_target prometheus_target")


def is_public(attribute, _):
    """If an attribute name starts with an underscore it is considered private"""
    return not attribute.name.startswith("_")


def is_writable(attribute):
    """Checks if an attribute is of type property and has a setter method"""
    return isinstance(attribute, property) and attribute.fset is not None


def get_exposable_metrics(metric_object):
    """Retrieves exposable attributes by checking if they are public"""
    metric_dict = asdict(metric_object, filter=is_public)
    all_attributes = vars(type(metric_object)).items()
    # include properties as they are not part of asdict
    properties = {n: p.__get__(metric_object) for n, p in all_attributes if isinstance(p, property)}
    metric_dict.update(properties)
    return metric_dict


def get_settable_metrics(metric_object):
    """Retrieves writable attributes by checking have a setter method"""
    metric_dict = asdict(metric_object)
    all_attributes = vars(type(metric_object)).items()
    # include properties as they are not part of asdict
    metric_dict.update({n: p.__get__(metric_object) for n, p in all_attributes if is_writable(p)})
    return metric_dict


@define(kw_only=True)
class Metric:
    """Base Metric class to track and expose statistics about logprep"""

    _labels: dict
    _prefix: str = "logprep_"

    def expose(self):
        """Iterates and collects all metrics and linked metrics in a common list."""
        exp = {}
        for attribute in get_exposable_metrics(self):
            attribute_value = self.__getattribute__(attribute)
            if isinstance(attribute_value, list):
                for value in attribute_value:
                    exp.update(value.expose())
            elif isinstance(attribute_value, Metric):
                exp.update(attribute_value.expose())
            else:
                labels = [":".join(item) for item in self._labels.items()]
                labels = ",".join(labels)
                metric_key = f"{self._prefix}{attribute}"
                exp[f"{metric_key};{labels}"] = float(attribute_value)
        return exp

    def reset_statistics(self):
        """Resets the statistics of self and children to 0"""
        for attribute in get_settable_metrics(self):
            attribute_value = self.__getattribute__(attribute)
            if isinstance(attribute_value, Metric):
                attribute_value = attribute_value.reset_statistics()
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
    return new_average, sample_counter
