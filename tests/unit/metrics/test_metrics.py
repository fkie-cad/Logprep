# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=protected-access

from prometheus_client import CollectorRegistry, Counter, generate_latest

import logprep.metrics.metrics as metrics
from logprep.metrics.metrics import CounterMetric

custom_registry = CollectorRegistry()

metrics.LOGPREP_REGISTRY = custom_registry


class TestsMetrics:
    def test_init_tracker_creates_metric(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
        )
        metric.init_tracker()
        assert isinstance(metric.tracker, Counter)

    def test_counter_metric_sets_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "pipeline-1"},
        )
        metric.init_tracker()
        assert metric.tracker._labelnames == ("pipeline",)
        assert ("pipeline-1",) in metric.tracker._metrics

    def test_counter_metric_increments_correctly(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
        )
        metric.init_tracker()
        metric += 1
        metric_output = generate_latest(custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 1.0' in metric_output
