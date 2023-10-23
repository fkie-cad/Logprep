# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import re

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from logprep.abc.component import Component
from logprep.metrics.metrics import CounterMetric, GaugeMetric, HistogramMetric


class TestsMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_tracker_returns_collector(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        assert isinstance(metric.tracker, Counter)

    def test_init_tracker_does_not_raise_if_initialized_twice(self):
        metric1 = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric2 = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        assert isinstance(metric1.tracker, Counter)
        assert isinstance(metric2.tracker, Counter)
        assert metric1.tracker == metric2.tracker

    def test_counter_metric_sets_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "pipeline-1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        assert metric.tracker._labelnames == ("pipeline",)

    def test_initialize_without_labels_initializes_defaults(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            registry=self.custom_registry,
        )
        assert len(metric.tracker._labelnames) == 4

    def test_initialize_with_empty_labels_raises(self):
        with pytest.raises(ValueError):
            _ = CounterMetric(
                name="bla",
                description="empty description",
                registry=self.custom_registry,
                labels={},
            )

    def test_counter_metric_increments_correctly(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 1.0' in metric_output

    def test_counter_metric_increments_twice(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
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
        metric2 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )

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
        metric2 = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "2"},
            registry=self.custom_registry,
        )

        assert metric1.tracker == metric2.tracker
        metric1 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 1\.0.*', metric_output)
        assert len(result) == 1
        result = re.findall(r'.*logprep_bla_total\{pipeline="2"\} 0\.0.*', metric_output)
        assert len(result) == 1

    def test_init_tracker_raises_on_try_to_overwrite_tracker_with_different_type(self):
        _ = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        with pytest.raises(ValueError, match="already exists with different type"):
            _ = HistogramMetric(
                name="bla",
                description="empty description",
                labels={"pipeline": "2"},
                registry=self.custom_registry,
            )


class TestComponentMetric:
    class Metrics(Component.Metrics):
        """test class"""

        test_metric_number_1: CounterMetric = CounterMetric(
            name="test_metric_number_1",
            description="empty description",
        )

        test_metric_without_label_values: CounterMetric = CounterMetric(
            name="test_metric_number_1",
            description="empty description",
            inject_label_values=False,
        )

    def setup_method(self):
        self.metrics = self.Metrics(labels={"label1": "value1", "label2": "value2"})

    def test_init(self):
        assert self.metrics.test_metric_number_1 is not None
        assert isinstance(self.metrics.test_metric_number_1, CounterMetric)
        assert self.metrics.test_metric_number_1.tracker is not None
        assert isinstance(self.metrics.test_metric_number_1.tracker, Counter)

    def test_label_values_injection(self):
        assert self.metrics.test_metric_number_1.tracker._labelnames == (
            "component",
            "name",
            "type",
            "description",
        )
        metric = self.metrics.test_metric_number_1
        metric_object = metric.tracker.collect()[0]
        assert len(metric_object.samples) == 2
        assert metric_object.samples[0][1] == {
            "component": "None",
            "name": "None",
            "type": "None",
            "description": "None",
        }

    def test_no_label_values_injection(self):
        assert self.metrics.test_metric_without_label_values.tracker._labelnames == (
            "component",
            "name",
            "type",
            "description",
        )
        metric = self.metrics.test_metric_without_label_values
        metric_object = metric.tracker.collect()[0]
        assert len(metric_object.samples) == 0
