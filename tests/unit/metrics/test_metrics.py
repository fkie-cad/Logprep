# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init


from prometheus_client import CollectorRegistry, Counter, generate_latest

from logprep.metrics import metrics
from logprep.metrics.metrics import CounterMetric


class TestsMetrics:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()
        metrics.LOGPREP_REGISTRY = self.custom_registry

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
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 1.0' in metric_output

    def test_counter_metric_increments_second(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
        )
        metric.init_tracker()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 2.0' in metric_output
