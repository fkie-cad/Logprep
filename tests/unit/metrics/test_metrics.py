# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import re
from unittest import mock

import pytest
from attrs import define, field
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from logprep.abc.component import Component
from logprep.metrics.metrics import CounterMetric, GaugeMetric, HistogramMetric, Metric


class TestMetric:
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
        metric1.init_tracker()
        metric2.init_tracker()
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
        with pytest.raises(ValueError, match="No label names were set when constructing"):
            metric.init_tracker()

    def test_initialize_with_empty_labels_initializes_default_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            registry=self.custom_registry,
            labels={},
        )
        with pytest.raises(ValueError, match="No label names were set when constructing"):
            metric.init_tracker()

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

    def test_counter_metric_increments_twice_adds_metric(self):
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

    def test_same_counter_counts_on_same_tracker(self):
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
        metric1.init_tracker()
        metric2.init_tracker()
        assert metric1.tracker._labelnames == metric2.tracker._labelnames
        metric1 += 1
        metric2 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 2\.0.*', metric_output)
        assert len(result) == 1

    def test_same_counter_with_different_label_values_counts_on_different_tracker(self):
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
        metric1.init_tracker()
        metric2.init_tracker()

        assert metric1.tracker == metric2.tracker
        metric1 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 1\.0.*', metric_output)
        assert len(result) == 1
        result = re.findall(r'.*logprep_bla_total\{pipeline="2"\} 0\.0.*', metric_output)
        assert len(result) == 1

    def test_init_tracker_raises_on_try_to_overwrite_tracker_with_different_type(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        with pytest.raises(ValueError, match="already exists with different type"):
            metric = HistogramMetric(
                name="bla",
                description="empty description",
                labels={"pipeline": "2"},
                registry=self.custom_registry,
            )
            metric.init_tracker()

    def test_add_with_labels_none_value_raises_typeerror(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        with pytest.raises(TypeError, match="not supported between instances of 'NoneType'"):
            metric.add_with_labels(None, {"A": "a"})

    def test_add_with_labels_none_labels_raises_typeerror(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        with pytest.raises(TypeError, match=" unsupported operand type(s) for |"):
            metric.add_with_labels(1, None)


class TestGaugeMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_tracker_returns_collector(self):
        metric = GaugeMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        assert isinstance(metric.tracker, Gauge)

    def test_gauge_metric_increments_correctly(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla{pipeline="1"} 1.0' in metric_output

    def test_gauge_metric_increment_twice_sets_metric(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla{pipeline="1"} 1.0' in metric_output


class TestHistogramMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_tracker_returns_collector(self):
        metric = HistogramMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        assert isinstance(metric.tracker, Histogram)

    def test_gauge_metric_increments_correctly(self):
        metric = HistogramMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert re.search(r'logprep_bla_sum\{pipeline="1"\} 1\.0', metric_output)
        assert re.search(r'logprep_bla_count\{pipeline="1"\} 1\.0', metric_output)
        assert re.search(r'logprep_bla_bucket\{le=".*",pipeline="1"\} \d+', metric_output)

    def test_gauge_metric_increment_twice_sets_metric(self):
        metric = HistogramMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_tracker()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert re.search(r'logprep_bla_sum\{pipeline="1"\} 2\.0', metric_output)
        assert re.search(r'logprep_bla_count\{pipeline="1"\} 2\.0', metric_output)
        assert re.search(r'logprep_bla_bucket\{le=".*",pipeline="1"\} \d+', metric_output)


class TestComponentMetrics:
    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """test class"""

        custom_registry = CollectorRegistry()

        test_metric_number_1: CounterMetric = field(
            factory=lambda: CounterMetric(
                name="test_metric_number_1",
                description="empty description",
                registry=TestComponentMetrics.Metrics.custom_registry,
            )
        )
        test_metric_without_label_values: CounterMetric = field(
            factory=lambda: CounterMetric(
                name="test_metric_number_1",
                description="empty description",
                inject_label_values=False,
                registry=TestComponentMetrics.Metrics.custom_registry,
            )
        )

        test_metric_histogram: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                name="test_metric_histogram",
                description="empty description",
                registry=TestComponentMetrics.Metrics.custom_registry,
            )
        )

    def setup_method(self):
        TestComponentMetrics.Metrics.custom_registry = CollectorRegistry()
        self.metrics = self.Metrics(
            labels={
                "component": "test",
                "name": "test",
                "type": "test_type",
                "description": "test_description",
            }
        )
        self.rule_type = "test_rule"

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
        metrics_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert (
            'logprep_test_metric_number_1_total{component="test",description="test_description",name="test",type="test_type"} 0.0'
            in metrics_output
        )
        assert '"None"' not in metrics_output, "default labels should not be present"

    def test_no_label_values_injection(self):
        assert self.metrics.test_metric_without_label_values.tracker._labelnames == (
            "component",
            "name",
            "type",
            "description",
        )
        metrics_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert "test_metric_without_label_values" not in metrics_output

    @mock.patch.dict("os.environ", {"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}, clear=True)
    def test_measure_time_measures_and_appends_processing_times_but_not_hostname(self):
        @Metric.measure_time(metric_name="test_metric_histogram")
        def decorated_function_append(self, document):
            pass

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 0\.0", metric_output)
        document = {"test": "event"}
        decorated_function_append(self, document)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert not re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 1\.0", metric_output)
        assert not re.search(
            r"test_metric_histogram_bucket.* 2\.0", metric_output
        )  # regex is greedy
        assert "processing_times" in document
        assert not "hostname" in document.get("processing_times")  # is only set by the pipeline
        assert "test_rule" in document.get("processing_times")
        assert document.get("processing_times").get("test_rule") > 0

    @mock.patch.dict("os.environ", {"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}, clear=True)
    def test_measure_time_measures_and_appends_processing_times_two_times(self):
        # simulates consecutive calls from processors that appear two times in
        # the pipeline, more precise two of the same rule_types appear in the
        # pipeline

        @Metric.measure_time(metric_name="test_metric_histogram")
        def decorated_function_append(self, document):
            pass

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 0\.0", metric_output)
        document = {"test": "event"}
        decorated_function_append(self, document)
        decorated_function_append(self, document)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert not re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 2\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 2\.0", metric_output)
        assert not re.search(
            r"test_metric_histogram_bucket.* 3\.0", metric_output
        )  # regex is greedy
        assert "processing_times" in document
        assert not "hostname" in document.get("processing_times")  # is only set by the pipeline
        assert "test_rule" in document.get("processing_times")
        assert document.get("processing_times").get("test_rule") > 0

    @mock.patch("logprep.metrics.metrics.gethostname", return_value="testhost")
    @mock.patch.dict("os.environ", {"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}, clear=True)
    def test_measure_time_measures_and_appends_pipeline_processing_times_and_hostname(
        self, mock_gethostname
    ):
        # set logprep_config to mimic an attribute of a pipeline, is used to identify pipelines
        self._logprep_config = "some value"

        @Metric.measure_time(metric_name="test_metric_histogram")
        def decorated_function_append(self, document):
            pass

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 0\.0", metric_output)
        document = {"test": "event"}
        decorated_function_append(self, document)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert not re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 1\.0", metric_output)
        assert not re.search(
            r"test_metric_histogram_bucket.* 2\.0", metric_output
        )  # regex is greedy
        assert "processing_times" in document
        assert "pipeline" in document.get("processing_times")
        assert "hostname" in document.get("processing_times")
        assert document.get("processing_times").get("pipeline") > 0
        assert document.get("processing_times").get("hostname") == "testhost"
        mock_gethostname.assert_called_once()

    def test_measure_time_measures(self):
        @Metric.measure_time(metric_name="test_metric_histogram")
        def decorated_function(self):
            pass

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 0\.0", metric_output)
        decorated_function(self)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert not re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        assert re.search(r"test_metric_histogram_bucket.* 1\.0", metric_output)
        assert not re.search(
            r"test_metric_histogram_bucket.* 2\.0", metric_output
        )  # regex is greedy

    @mock.patch("time.perf_counter", side_effect=[1, 2])
    def test_measure_time_measures_but_does_not_append_to_empty_events(self, mock_perf_counter):
        mock_env = {"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}
        with mock.patch.dict("os.environ", mock_env):

            @Metric.measure_time(metric_name="test_metric_histogram")
            def decorated_function_append(self, document):
                pass

            metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
            assert re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
            assert re.search(r"test_metric_histogram_count.* 0\.0", metric_output)
            assert re.search(r"test_metric_histogram_bucket.* 0\.0", metric_output)
            document = {}
            decorated_function_append(self, document)

            metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
            assert not re.search(r"test_metric_histogram_sum.* 0\.0", metric_output)
            assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
            assert re.search(r"test_metric_histogram_bucket.* 1\.0", metric_output)
            assert not re.search(
                r"test_metric_histogram_bucket.* 2\.0", metric_output
            )  # regex is greedy
            assert document == {}
            # assert call on time.perf_counter to ensure that the correct decorator was accessed
            mock_perf_counter.assert_called()
