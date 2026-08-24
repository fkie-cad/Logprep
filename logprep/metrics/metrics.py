"""
Logprep provides a prometheus exporter with certain processing and connector metrics, e.g.
:code:`logprep_number_of_processed_events_total` or :code:`logprep_processing_time_per_event_sum`.

Examples of grafana dashboards can be found in `the logprep github repo
<https://github.com/fkie-cad/Logprep/tree/main/examples/exampledata/config/grafana/dashboards>`_

Configuration
=============

Example
-------

..  code-block:: yaml
    :linenos:

    metrics:
      enabled: true
      port: 8000


The metrics configuration offers some options regarding the metrics export. Because logprep utilizes
the `prometheus python client <https://github.com/prometheus/client_python>`_ the environment
variable :code:`PROMETHEUS_MULTIPROC_DIR` is required to be set by the user. This is a temporary
directory where logprep will store files needed for in-between process communication. This folder
has to be provided by the user because logprep won't create it.

enabled
-------

Use :code:`true` or :code:`false` to activate or deactivate the metrics exporter. Defaults to
:code:`false`.

port
----

Specifies the port which should be used for the prometheus exporter endpoint. Defaults to
:code:`8000`.

Processing Times in Events
==========================

It is also possible to add processing times of each processor to the event
itself. The processing times can then be found in the field :code:`processing_time` of each
processed event. Additionally, the hostname of the machine on which Logprep runs is listed.
To activate this feature you have to set the environment variable
:code:`LOGPREP_APPEND_MEASUREMENT_TO_EVENT` with any value. This divergence of the usual
configuration pattern is needed due to performance reasons.

Metrics Overview
================

General Metrics
---------------

.. autoclass:: logprep.runner.Runner.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.framework.pipeline.Pipeline.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.abc.connector.Connector.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.processor.base.rule.Rule.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:


Connector Specific
------------------

.. autoclass:: logprep.connector.confluent_kafka.input.ConfluentKafkaInput.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.connector.confluent_kafka.output.ConfluentKafkaOutput.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

Processor Specific Metrics
--------------------------

.. autoclass:: logprep.processor.amides.processor.Amides.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.processor.domain_resolver.processor.DomainResolver.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.processor.pseudonymizer.processor.Pseudonymizer.Metrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:
"""

import functools
import inspect
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, Self, TypeVar

import attrs
from _socket import gethostname
from attrs import define, field, validators
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.metrics import MetricWrapperBase
from prometheus_client.samples import Sample

from logprep.util.environ import ENV_VARS
from logprep.util.helper import _add_field_to_silent_fail

M = TypeVar("M", bound=MetricWrapperBase)


def _collector_method(func):
    """
    Marks a metric method as a 1:1 wrapper of the underlying collector method.
    The wrapper is then automatically replaced with the bound child method.
    This happens either eagerly on init or lazily (see :code:`Metric._bind(...)`).
    """
    func.__collector_method__ = True
    return func


@define(kw_only=True, slots=False)
class Metric(ABC, Generic[M]):
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
        factory=dict,
    )
    inject_label_values: bool = field(default=True)
    """
    Registers the labels with metric 0 in :code:`init_collector`.
    Otherwise registration takes place on first metric increment.
    """

    _prefix: str = field(default="logprep_")
    _registry: CollectorRegistry | None = field(default=None)

    _collector: M = field(default=None, init=False)

    _collector_methods: ClassVar[set[str]]
    """Methods marked as tracked method collected on subclass init"""

    _value_series_suffix: ClassVar[str]
    """Suffix implemented by subclasses to select the right series carrying the metric value"""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._collector_methods = {
            name
            for klass in cls.__mro__
            for name, value in vars(klass).items()
            if getattr(value, "__collector_method__", False)
        }

    def __attrs_post_init__(self):
        if self._registry is not None:
            return

        # When this environment variable is set,
        # the prometheus_client will automatically run in multiprocessing mode
        # In that mode it is not allowed to set a Registry specifically.
        # For the non multiprocessing mode,
        # we need to set a Registry otherwise our custom metrics never get
        # registered and then subsequently cannot be exported
        if ENV_VARS.get("PROMETHEUS_MULTIPROC_DIR", "") != "":
            self._registry = None
        else:
            self._registry = REGISTRY

    @property
    @abstractmethod
    def collector_type(self) -> type[M]:
        """The prometheus metric companion type"""

    @property
    def fullname(self):
        """returns the fullname"""
        return f"{self._prefix}{self.name}"

    def init_collector(self) -> None:
        """initializes the collector and registers it"""
        try:
            self._collector = self._init_collector()
        except ValueError as error:
            # pylint: disable=protected-access
            collector = None
            if self._registry:
                # recover by getting the existing instance, which is the likely error source
                collector = self._registry._names_to_collectors.get(self.fullname)
            # pylint: enable=protected-access
            if collector is None:
                raise
            if not isinstance(collector, self.collector_type):
                raise ValueError(
                    f"Metric {self.fullname} already exists with different type"
                ) from error
            self._collector = collector
        if self.inject_label_values:
            self._bind(self._labeled_child(self.labels))

    @property
    def initialized(self) -> bool:
        """Whether :code:`init_collector` has been called successfully"""
        return self._collector is not None

    def _labeled_child(self, labels: dict[str, str]) -> M:
        """Return the labelled child of the collector for the given labels"""
        return self._collector.labels(**(self.labels | labels))

    def _bind(self, child: M) -> Self:
        """Bind the child's exposed methods directly onto this instance"""
        for name in self._collector_methods:
            setattr(self, name, getattr(child, name))
        return self

    def _lazy_bind_default_child(self) -> Self:
        """Bind the default child on first use and return the metric."""
        return self._bind(self._labeled_child(self.labels))

    def child_collector(self, labels: dict[str, str], inject_label_values: bool = True) -> Self:
        """Return a child metric configured with the given labels"""
        child = attrs.evolve(
            self, labels=self.labels | labels, inject_label_values=inject_label_values
        )
        child.init_collector()
        return child

    @abstractmethod
    def _init_collector(self) -> M:
        """Create the concrete prometheus metric object"""

    @property
    def value(self) -> float:
        """The value this metric currently exports, summed over its labelled children."""
        series_name = f"{self.fullname}{self._value_series_suffix}"
        return sum(sample.value for sample in self.collect_samples() if sample.name == series_name)

    def collect_samples(self) -> list[Sample]:
        """Return the samples of the whole collector, including every labelled child."""
        metrics = self._collector.collect()
        assert isinstance(metrics, list) and len(metrics) == 1, ".collect() implementation changed"
        return metrics[0].samples

    @staticmethod
    def measure_time(metric_name: str = "processing_time_per_event", self_arg: int = 0):
        """Decorate function to measure execution time for function and add results to event."""

        perf_counter = time.perf_counter
        append_to_event = bool(ENV_VARS.get("LOGPREP_APPEND_MEASUREMENT_TO_EVENT"))

        def decorator(func):
            is_async = inspect.iscoroutinefunction(func)

            if not append_to_event:

                @functools.wraps(func)
                async def timed_async(*args, **kwargs):
                    self = args[self_arg]
                    begin = perf_counter()
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        duration = perf_counter() - begin
                        getattr(self.metrics, metric_name).observe(duration)

                @functools.wraps(func)
                def timed(*args, **kwargs):
                    self = args[self_arg]
                    begin = perf_counter()
                    try:
                        return func(*args, **kwargs)
                    finally:
                        duration = perf_counter() - begin
                        getattr(self.metrics, metric_name).observe(duration)

                return timed_async if is_async else timed

            def append_measurement(self, args, duration: float) -> None:
                # TODO refactor measure_time for ng reducing implicit logic relying on hasattr
                is_rule = hasattr(self, "rule_type")
                is_pipeline = hasattr(self, "_logprep_config")
                if not (is_rule or is_pipeline):
                    return
                event = args[self_arg + 1]
                if not event:
                    return
                if is_rule:
                    _add_field_to_silent_fail(
                        event=event,
                        field=(f"processing_times.{self.rule_type}", duration),
                        rule=None,
                    )
                if is_pipeline:
                    _add_field_to_silent_fail(
                        event=event, field=("processing_times.pipeline", duration), rule=None
                    )
                    _add_field_to_silent_fail(
                        event=event, field=("processing_times.hostname", gethostname()), rule=None
                    )

            @functools.wraps(func)
            async def timed_and_appended_async(*args, **kwargs):
                self = args[self_arg]
                begin = perf_counter()
                try:
                    result = await func(*args, **kwargs)
                finally:
                    duration = perf_counter() - begin
                    getattr(self.metrics, metric_name).observe(duration)
                append_measurement(self, args, duration)
                return result

            @functools.wraps(func)
            def timed_and_appended(*args, **kwargs):
                self = args[self_arg]
                begin = perf_counter()
                try:
                    result = func(*args, **kwargs)
                finally:
                    duration = perf_counter() - begin
                    getattr(self.metrics, metric_name).observe(duration)
                append_measurement(self, args, duration)
                return result

            return timed_and_appended_async if is_async else timed_and_appended

        return decorator


@define(kw_only=True)
class CounterMetric(Metric[Counter]):
    """Wrapper for prometheus Counter metric"""

    _value_series_suffix: ClassVar[str] = "_total"
    """A counter exports its value under the `_total` series"""

    @property
    def collector_type(self) -> type[Counter]:
        return Counter

    def _init_collector(self):
        return Counter(
            name=self.fullname,
            documentation=self.description,
            labelnames=self.labels.keys(),
            registry=self._registry,
        )

    @_collector_method
    def inc(self, amount: float = 1, exemplar: dict[str, str] | None = None) -> None:
        """Increment the counter. Rebinds to the collector's method on first call."""
        return self._lazy_bind_default_child().inc(amount, exemplar)

    def add_with_labels(self, other: Any, labels: dict) -> None:
        """Deprecated method. Always creates a metric with labels set and adds/sets the value"""
        self._labeled_child(labels).inc(other)


@define(kw_only=True)
class HistogramMetric(Metric[Histogram]):
    """Wrapper for prometheus Histogram metric"""

    _value_series_suffix: ClassVar[str] = "_sum"
    """The histogram value is the sum of the observations"""

    @property
    def count(self) -> float:
        """How many observations were made, summed over the labelled children"""
        series = f"{self.fullname}_count"
        return sum(sample.value for sample in self.collect_samples() if sample.name == series)

    @property
    def collector_type(self) -> type[Histogram]:
        return Histogram

    def _init_collector(self):
        return Histogram(
            name=self.fullname,
            documentation=self.description,
            labelnames=self.labels.keys(),
            buckets=(0.00001, 0.00005, 0.0001, 0.001, 0.1, 1),
            registry=self._registry,
        )

    @_collector_method
    def observe(self, amount: float, exemplar: dict[str, str] | None = None) -> None:
        """Observe a value. Rebinds to the collector's method on first call."""
        return self._lazy_bind_default_child().observe(amount, exemplar)

    def add_with_labels(self, other: Any, labels: dict) -> None:
        """Deprecated method. Always creates a metric with labels set and adds/sets the value"""
        self._labeled_child(labels).observe(other)


@define(kw_only=True)
class GaugeMetric(Metric[Gauge]):
    """Wrapper for prometheus Gauge metric"""

    _value_series_suffix: ClassVar[str] = ""
    """A gauge exports its value under the bare metric name, without a suffix"""

    @property
    def collector_type(self) -> type[Gauge]:
        return Gauge

    def _init_collector(self) -> Gauge:
        return Gauge(
            name=self.fullname,
            documentation=self.description,
            labelnames=self.labels.keys(),
            registry=self._registry,
            multiprocess_mode="liveall",
        )

    @_collector_method
    def set(self, value: float) -> None:
        """Set the gauge. Rebinds to the collector's method on first call"""
        return self._lazy_bind_default_child().set(value)

    @_collector_method
    def inc(self, amount: float = 1) -> None:
        """Increment the gauge. Rebinds to the collector's method on first call"""
        return self._lazy_bind_default_child().inc(amount)

    @_collector_method
    def dec(self, amount: float = 1) -> None:
        """Decrement the gauge. Rebinds to the collector's method on first call"""
        return self._lazy_bind_default_child().dec(amount)

    def add_with_labels(self, other: Any, labels: dict) -> None:
        """Deprecated method. Always creates a metric with labels set and adds/sets the value"""
        self._labeled_child(labels).set(other)
