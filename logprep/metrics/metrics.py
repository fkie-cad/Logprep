"""This module tracks, calculates, exposes and resets logprep metrics"""
from abc import ABC, abstractmethod

from attr import define, field, validators
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


@define(kw_only=True)
class Metric(ABC):
    """Metric base class"""

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
    trackers: dict = None
    _registry: CollectorRegistry = field(default=None)
    _prefix: str = field(default="logprep_")

    @property
    def fullname(self):
        """returns the fullname"""
        return f"{self._prefix}{self.name}"

    def init_tracker(self):
        """initializes the tracker and adds it to the trackers dict"""
        tracker = None
        try:
            if isinstance(self, CounterMetric):
                tracker = Counter(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    registry=self._registry,
                )
            if isinstance(self, HistogramMetric):
                tracker = Histogram(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    buckets=(0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1),
                    registry=self._registry,
                )
            if isinstance(self, GaugeMetric):
                tracker = Gauge(
                    name=self.fullname,
                    documentation=self.description,
                    labelnames=self.labels.keys(),
                    registry=self._registry,
                    multiprocess_mode="liveall",
                )
            tracker.labels(**self.labels)

            self.trackers.update({self.fullname: tracker})
        except ValueError:
            self.trackers.get(self.fullname).labels(**self.labels)

    @abstractmethod
    def __add__(self, other):
        """Add"""


@define(kw_only=True)
class CounterMetric(Metric):
    """Wrapper for prometheus Counter metric"""

    trackers: dict = {}

    def __add__(self, other):
        return self.add_with_labels(other, self.labels)

    def add_with_labels(self, other, labels):
        """Add with labels"""
        labels = self.labels | labels
        self.trackers.get(self.fullname).labels(**labels).inc(other)
        return self


@define(kw_only=True)
class HistogramMetric(Metric):
    """Wrapper for prometheus Histogram metric"""

    trackers: dict = {}

    def __add__(self, other):
        self.trackers.get(self.fullname).labels(**self.labels).observe(other)
        return self


@define(kw_only=True)
class GaugeMetric(Metric):
    """Wrapper for prometheus Gauge metric""" ""

    trackers: dict = {}

    def __add__(self, other):
        return self.add_with_labels(other, self.labels)

    def add_with_labels(self, other, labels):
        """Add with labels"""
        labels = self.labels | labels
        self.trackers.get(self.fullname).labels(**labels).set(other)
        return self
