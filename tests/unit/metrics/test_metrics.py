# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=protected-access
from typing import List

import numpy as np
from prometheus_client import REGISTRY
from prometheus_client.registry import Collector

from logprep.metrics.metrics import CounterMetric, MetricType


class TestsMetrics:
    def test_converts_enum_to_prometheus_metric(self):
        metric = CounterMetric(
            name="testmetric",
            type=MetricType.COUNTER,
            description="empty description",
            labels={"A": "a"},
        )
        assert issubclass(metric.type, Collector)

    def test_counter_metric_sets_labels(self):
        metric = CounterMetric(
            type=MetricType.COUNTER,
            name="bla",
            description="empty description",
            labels={"pipeline": "pipeline-1"},
        )
        assert metric.tracker._labelnames == ("pipeline",)
        assert ("pipeline-1",) in metric.tracker._metrics

    def test_counter_metric_increments_correctly(self):
        metric = CounterMetric(
            type=MetricType.COUNTER,
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
        )
        metric += 1
        assert list(REGISTRY.collect())[-1].samples[-2].value == 1
        assert metric is not None
