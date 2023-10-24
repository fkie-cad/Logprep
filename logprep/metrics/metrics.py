"""This module tracks, calculates, exposes and resets logprep metrics"""
from abc import ABC, abstractmethod
from typing import Union

from attr import define, field, validators
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


def get_default_labels():
    """returns the default labels"""
    return {"component": None, "name": None, "type": None, "description": None}


@define(kw_only=True, slots=False)
class Metric(ABC):
    """Metric base class"""

    name: str = field(validator=validators.instance_of(str))
    description: str = field(validator=validators.instance_of(str))
    labels: dict = field(
        validator=[
            validators.instance_of(dict),
            validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of((str, type(None))),
            ),
        ],
        factory=dict,
    )
    _registry: CollectorRegistry = field(default=None)
    _prefix: str = field(default="logprep_")
    inject_label_values: bool = field(default=True)
    tracker: Union[Counter, Histogram, Gauge] = field(init=False, default=None)

    @property
    def fullname(self):
        """returns the fullname"""
        return f"{self._prefix}{self.name}"

    def init_tracker(self) -> None:
        """initializes the tracker and adds it to the trackers dict"""
        if not self.labels:
            self.labels = get_default_labels()
        try:
            if isinstance(self, CounterMetric):
                self.tracker = Counter(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    registry=self._registry,
                )
            if isinstance(self, HistogramMetric):
                self.tracker = Histogram(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    buckets=(0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1),
                    registry=self._registry,
                )
            if isinstance(self, GaugeMetric):
                self.tracker = Gauge(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    registry=self._registry,
                    multiprocess_mode="liveall",
                )
        except ValueError as error:
            # pylint: disable=protected-access
            self.tracker = self._registry._names_to_collectors.get(self.fullname)
            # pylint: enable=protected-access
            if not isinstance(self.tracker, METRIC_TO_COLLECTOR_TYPE[type(self)]):
                raise ValueError(
                    f"Metric {self.fullname} already exists with different type"
                ) from error
        if None not in list(self.labels.values()):
            self.tracker.labels(**self.labels)

    @abstractmethod
    def __add__(self, other):
        """Add"""

    @staticmethod
    def measure_time(metric_name: str = "processing_time_per_event"):
        """Decorate function to measure execution time for function and add results to event."""

        def inner_decorator(func):
            def inner(self, *args, **kwargs):  # nosemgrep
                metric = getattr(self.metrics, metric_name)
                with metric.tracker.labels(**metric.labels).time():
                    result = func(self, *args, **kwargs)
                return result

            return inner

        return inner_decorator


@define(kw_only=True)
class CounterMetric(Metric):
    """Wrapper for prometheus Counter metric"""

    def __add__(self, other):
        return self.add_with_labels(other, self.labels)

    def add_with_labels(self, other, labels):
        """Add with labels"""
        labels = self.labels | labels
        self.tracker.labels(**labels).inc(other)
        return self


@define(kw_only=True)
class HistogramMetric(Metric):
    """Wrapper for prometheus Histogram metric"""

    def __add__(self, other):
        self.tracker.labels(**self.labels).observe(other)
        return self


@define(kw_only=True)
class GaugeMetric(Metric):
    """Wrapper for prometheus Gauge metric""" ""

    def __add__(self, other):
        return self.add_with_labels(other, self.labels)

    def add_with_labels(self, other, labels):
        """Add with labels"""
        labels = self.labels | labels
        self.tracker.labels(**labels).set(other)
        return self


METRIC_TO_COLLECTOR_TYPE = {
    CounterMetric: Counter,
    HistogramMetric: Histogram,
    GaugeMetric: Gauge,
}
