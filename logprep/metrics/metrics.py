"""This module tracks, calculates, exposes and resets logprep metrics"""
from enum import Enum

from attr import asdict, define, field, validators
from prometheus_client import Counter, Gauge, Histogram, Info


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


class MetricType(Enum):
    COUNTER = 1
    HISTOGRAM = 2
    GAUGE = 3
    INFO = 4


PROMETHEUS_METRIC_TYPES = {
    MetricType.COUNTER.value: Counter,
    MetricType.GAUGE.value: Gauge,
    MetricType.INFO.value: Info,
    MetricType.HISTOGRAM.value: Histogram,
}


@define(kw_only=True)
class Metric:
    type: MetricType = field(converter=lambda x: PROMETHEUS_METRIC_TYPES.get(x.value))
    name: str = field(validator=validators.instance_of(str))
    description: str = field(validator=validators.instance_of(str))
    labels: dict = field(
        validator=[
            validators.instance_of(dict),
            validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of(str),
            ),
        ]
    )
    tracker: object = field(default=None)

    def __add__(self, other):
        self.tracker.labels(**self.labels).inc(other)
        return self


def calculate_new_average(current_average, next_sample, sample_counter):
    """Calculate a new average by combining a new sample with a sample counter"""
    average_multiple = current_average * sample_counter
    extended_average_multiple = average_multiple + next_sample
    sample_counter += 1
    new_average = extended_average_multiple / sample_counter
    return new_average, sample_counter
