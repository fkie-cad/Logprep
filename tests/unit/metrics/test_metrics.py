# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import re

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from logprep.metrics.metrics import CounterMetric, GaugeMetric, HistogramMetric


class TestsMetrics:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_tracker_returns_collector(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        assert isinstance(metric.tracker, Counter)

    def test_init_tracker_does_not_raise_if_initialized_twice(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        assert metric.init_tracker() == metric.init_tracker()
        assert isinstance(metric.tracker, Counter)

    def test_counter_metric_sets_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "pipeline-1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        assert metric.tracker._labelnames == ("pipeline",)

    def test_counter_metric_increments_correctly(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
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
            registry=self.custom_registry,
        )
        metric.init_tracker()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 2.0' in metric_output

    def test_no_duplicated_counter_is_created(self):
        metric1 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric1.init_tracker()
        metric2 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric2.init_tracker()

        assert metric1.tracker._labelnames == metric2.tracker._labelnames
        metric1 += 1
        metric2 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 2\.0.*', metric_output)
        assert len(result) == 1

    def test_no_duplicated_counter_is_created_2(self):
        metric1 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric1.init_tracker()
        metric2 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "2"},
            registry=self.custom_registry,
        )
        metric2.init_tracker()

        assert metric1.tracker == metric2.tracker
        metric1 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 1\.0.*', metric_output)
        assert len(result) == 1
        result = re.findall(r'.*logprep_bla_total\{pipeline="2"\} 0\.0.*', metric_output)
        assert len(result) == 1

    def test_init_tracker_raises_on_try_to_overwrite_tracker_with_different_type(self):
        metric1 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric1.init_tracker()
        metric2 = HistogramMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "2"},
            registry=self.custom_registry,
        )
        with pytest.raises(ValueError, match="already exists with different type"):
            metric2.init_tracker()
