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

import os
import time
from _socket import gethostname
from abc import ABC, abstractmethod
from typing import Any, Union

from attrs import define, field, validators
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from logprep.util.helper import _add_field_to_silent_fail


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
                value_validator=validators.instance_of(str),
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
                    buckets=(0.00001, 0.00005, 0.0001, 0.001, 0.1, 1),
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
        if self.inject_label_values:
            self.tracker.labels(**self.labels)

    @abstractmethod
    def __add__(self, other):
        """Add"""

    @staticmethod
    def measure_time(metric_name: str = "processing_time_per_event"):
        """Decorate function to measure execution time for function and add results to event."""

        if not os.environ.get("LOGPREP_APPEND_MEASUREMENT_TO_EVENT"):

            def without_append(func):
                def inner(self, *args, **kwargs):  # nosemgrep
                    metric = getattr(self.metrics, metric_name)
                    with metric.tracker.labels(**metric.labels).time():
                        result = func(self, *args, **kwargs)
                    return result

                return inner

            return without_append

        def with_append(func):
            def inner(self, *args, **kwargs):  # nosemgrep
                metric = getattr(self.metrics, metric_name)
                begin = time.perf_counter()
                result = func(self, *args, **kwargs)
                duration = time.perf_counter() - begin
                metric += duration

                if hasattr(self, "rule_type"):
                    event = args[0]
                    if event:
                        _add_field_to_silent_fail(
                            event=event,
                            field=(f"processing_times.{self.rule_type}", duration),
                            rule=None,
                        )
                if hasattr(self, "_logprep_config"):  # attribute of the Pipeline class
                    event = args[0]
                    if event:
                        _add_field_to_silent_fail(
                            event=event, field=("processing_times.pipeline", duration), rule=None
                        )
                        _add_field_to_silent_fail(
                            event=event,
                            field=("processing_times.hostname", gethostname()),
                            rule=None,
                        )
                return result

            return inner

        return with_append


@define(kw_only=True)
class CounterMetric(Metric):
    """Wrapper for prometheus Counter metric"""

    def __add__(self, other: Any) -> "CounterMetric":
        return self.add_with_labels(other, self.labels)

    def add_with_labels(self, other: Any, labels: dict) -> "CounterMetric":
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
