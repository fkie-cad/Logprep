"""This module tracks, calculates, exposes and resets logprep metrics"""
from abc import ABC, abstractmethod
from typing import Callable

from attr import asdict, define, field, validators
from prometheus_client import Counter, Histogram

LOGPREP_REGISTRY = None  # to inject a custom registry


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
class Metric(ABC):
    name: str = field(validator=validators.instance_of(str))
    description: str = field(validator=validators.instance_of(str))
    labels: dict = field(
        validator=[
            validators.instance_of(dict),
            validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of(str),
            ),
        ],
        default={},
    )
    tracker: object = field(default=None)
    target: Callable = field(default=None)
    _prefix: str = "logprep_"

    def init_tracker(self):
        tracker = None
        if isinstance(self, CounterMetric):
            tracker = Counter(
                name=f"{self._prefix}{self.name}",
                documentation=self.description,
                labelnames=self.labels.keys(),
                registry=LOGPREP_REGISTRY,
            )
        if isinstance(self, HistogramMetric):
            tracker = Histogram(
                name=f"{self._prefix}{self.name}",
                documentation=self.description,
                labelnames=self.labels.keys(),
                buckets=(0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1),
                registry=LOGPREP_REGISTRY,
            )
        tracker.labels(**self.labels)
        self.tracker = tracker

    @abstractmethod
    def __add__(self, other):
        """Add"""


@define(kw_only=True)
class CounterMetric(Metric):
    def __add__(self, other):
        self.tracker.labels(**self.labels).inc(other)
        return self


@define(kw_only=True)
class HistogramMetric(Metric):
    def __add__(self, other):
        self.tracker.labels(**self.labels).observe(other)
        return self


def calculate_new_average(current_average, next_sample, sample_counter):
    """Calculate a new average by combining a new sample with a sample counter"""
    average_multiple = current_average * sample_counter
    extended_average_multiple = average_multiple + next_sample
    sample_counter += 1
    new_average = extended_average_multiple / sample_counter
    return new_average, sample_counter
