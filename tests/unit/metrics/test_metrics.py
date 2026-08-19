# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import asyncio
import re
from unittest import mock

import pytest
from attrs import define, field
from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from logprep.abc.component import Component
from logprep.metrics.metrics import CounterMetric, GaugeMetric, HistogramMetric, Metric
from tests.conftest import mock_env


class TestMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_collector_returns_collector(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert isinstance(metric._collector, Counter)

    def test_init_collector_does_not_raise_if_initialized_twice(self):
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
        metric1.init_collector()
        metric2.init_collector()
        assert isinstance(metric1._collector, Counter)
        assert isinstance(metric2._collector, Counter)
        assert metric1._collector == metric2._collector

    def test_init_collector_reuses_collector_from_default_registry(self):
        metric1 = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
        )
        metric2 = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
        )
        metric1.init_collector()
        metric2.init_collector()

        assert metric1._collector == metric2._collector
        assert REGISTRY._names_to_collectors[metric1.fullname] == metric1._collector

    def test_counter_metric_sets_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "pipeline-1"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert metric._collector._labelnames == ("pipeline",)

    def test_initialize_without_labels_initializes_defaults(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            registry=self.custom_registry,
        )
        with pytest.raises(ValueError, match="No label names were set when constructing"):
            metric.init_collector()

    def test_initialize_with_empty_labels_initializes_default_labels(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            registry=self.custom_registry,
            labels={},
        )
        with pytest.raises(ValueError, match="No label names were set when constructing"):
            metric.init_collector()

    def test_counter_metric_increments_correctly(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_collector()
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
        metric.init_collector()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla_total{pipeline="1"} 2.0' in metric_output

    def test_same_counter_counts_on_same_collector(self):
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
        metric1.init_collector()
        metric2.init_collector()
        assert metric1._collector._labelnames == metric2._collector._labelnames
        metric1 += 1
        metric2 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 2\.0.*', metric_output)
        assert len(result) == 1

    def test_same_counter_with_different_label_values_counts_on_different_collector(self):
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
        metric1.init_collector()
        metric2.init_collector()

        assert metric1._collector == metric2._collector
        metric1 += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        result = re.findall(r'.*logprep_bla_total\{pipeline="1"\} 1\.0.*', metric_output)
        assert len(result) == 1
        result = re.findall(r'.*logprep_bla_total\{pipeline="2"\} 0\.0.*', metric_output)
        assert len(result) == 1

    def test_init_collector_raises_on_try_to_overwrite_collector_with_different_type(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        with pytest.raises(ValueError, match="already exists with different type"):
            metric = HistogramMetric(
                name="bla",
                description="empty description",
                labels={"pipeline": "2"},
                registry=self.custom_registry,
            )
            metric.init_collector()

    def test_initialized_is_true_only_after_init_collector(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        assert not metric.initialized
        metric.init_collector()
        assert metric.initialized

    @pytest.mark.parametrize(
        "metric_class, method, argument, expected",
        [
            (CounterMetric, "inc", 3, 'logprep_bla_total{A="a"} 3.0'),
            (GaugeMetric, "set", 5, 'logprep_bla{A="a"} 5.0'),
            (GaugeMetric, "inc", 2, 'logprep_bla{A="a"} 2.0'),
            (GaugeMetric, "dec", 2, 'logprep_bla{A="a"} -2.0'),
            (HistogramMetric, "observe", 0.5, 'logprep_bla_count{A="a"} 1.0'),
        ],
    )
    def test_collector_methods_write_to_the_default_child(
        self, metric_class, method, argument, expected
    ):
        metric = metric_class(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        getattr(metric, method)(argument)
        assert expected in generate_latest(self.custom_registry).decode("utf-8")

    @pytest.mark.parametrize(
        "metric_class, expected_methods",
        [
            (CounterMetric, {"inc"}),
            (GaugeMetric, {"set", "inc", "dec"}),
            (HistogramMetric, {"observe", "time"}),
        ],
    )
    def test_collector_methods_are_bound_onto_the_instance(self, metric_class, expected_methods):
        metric = metric_class(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        assert metric_class._collector_methods == expected_methods
        assert not expected_methods & metric.__dict__.keys()
        metric.init_collector()
        assert expected_methods <= metric.__dict__.keys()

    @pytest.mark.parametrize(
        "metric_class, method, argument, expected",
        [
            (CounterMetric, "inc", 3, 'logprep_bla_total{A="a"} 3.0'),
            (GaugeMetric, "set", 5, 'logprep_bla{A="a"} 5.0'),
            (GaugeMetric, "inc", 2, 'logprep_bla{A="a"} 2.0'),
            (GaugeMetric, "dec", 2, 'logprep_bla{A="a"} -2.0'),
            (HistogramMetric, "observe", 0.5, 'logprep_bla_count{A="a"} 1.0'),
        ],
    )
    def test_collector_methods_bind_lazily_without_label_injection(
        self, metric_class, method, argument, expected
    ):
        metric = metric_class(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            inject_label_values=False,
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert method not in metric.__dict__
        assert 'A="a"' not in generate_latest(self.custom_registry).decode("utf-8")
        # the fallback on the class runs once, then replaces itself
        getattr(metric, method)(argument)
        assert method in metric.__dict__
        assert expected in generate_latest(self.custom_registry).decode("utf-8")

    def test_histogram_time_binds_lazily_without_label_injection(self):
        metric = HistogramMetric(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            inject_label_values=False,
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert "time" not in metric.__dict__
        with metric.time():
            pass
        assert "time" in metric.__dict__
        assert 'logprep_bla_count{A="a"} 1.0' in generate_latest(self.custom_registry).decode(
            "utf-8"
        )

    @pytest.mark.parametrize(
        "metric_class, expected",
        [
            (CounterMetric, 'logprep_bla_total{A="first"} 2.0'),
            (GaugeMetric, 'logprep_bla{A="first"} 2.0'),
            (HistogramMetric, 'logprep_bla_count{A="first"} 1.0'),
        ],
    )
    def test_add_with_labels_writes_to_the_given_labels(self, metric_class, expected):
        metric = metric_class(
            name="bla",
            description="empty description",
            labels={"A": ""},
            inject_label_values=False,
            registry=self.custom_registry,
        )
        metric.init_collector()
        metric.add_with_labels(2, {"A": "first"})
        assert expected in generate_latest(self.custom_registry).decode("utf-8")

    @pytest.mark.parametrize(
        "registry_is_set", [True, False], ids=["with_registry", "without_registry"]
    )
    def test_init_collector_reraises_if_it_cannot_recover(self, registry_is_set):
        # the handler only recovers a collector that is already registered
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry if registry_is_set else None,
        )
        metric._registry = self.custom_registry if registry_is_set else None
        with mock.patch.object(
            metric, "_init_collector", side_effect=ValueError("unrelated failure")
        ):
            with pytest.raises(ValueError, match="unrelated failure"):
                metric.init_collector()
        assert not metric.initialized

    def test_registry_is_not_set_in_multiprocess_mode(self):
        with mock_env({"PROMETHEUS_MULTIPROC_DIR": "/tmp"}):
            metric = CounterMetric(name="bla", description="empty description", labels={"A": "a"})
        assert metric._registry is None

    def test_add_works_without_label_injection(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            inject_label_values=False,
            registry=self.custom_registry,
        )
        metric.init_collector()
        metric += 2
        assert 'logprep_bla_total{A="a"} 2.0' in generate_latest(self.custom_registry).decode(
            "utf-8"
        )

    def test_collect_samples_returns_labels_and_values(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        metric += 3
        samples = [sample for sample in metric.collect_samples() if sample.name.endswith("_total")]
        assert [(sample.labels, sample.value) for sample in samples] == [({"A": "a"}, 3.0)]

    def test_collect_samples_returns_every_labeled_child(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"A": ""},
            registry=self.custom_registry,
            inject_label_values=False,
        )
        metric.init_collector()
        metric.add_with_labels(1, {"A": "first"})
        metric.add_with_labels(2, {"A": "second"})
        samples = [sample for sample in metric.collect_samples() if sample.name.endswith("_total")]
        assert {sample.labels["A"]: sample.value for sample in samples} == {
            "first": 1.0,
            "second": 2.0,
        }

    def test_collect_samples_on_uninitialized_metric_raises(self):
        metric = CounterMetric(
            name="bla",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        with pytest.raises(AttributeError):
            metric.collect_samples()

    def test_child_collector_returns_initialized_child(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"A": "a", "B": ""},
            registry=self.custom_registry,
        )
        metric.init_collector()
        child = metric.child_collector({"B": "b"})
        assert child.initialized
        assert child._collector is metric._collector
        assert child.labels == {"A": "a", "B": "b"}

    def test_child_collector_writes_to_its_own_labels(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"A": "a", "B": ""},
            registry=self.custom_registry,
        )
        metric.init_collector()
        metric.child_collector({"B": "first"}).set(1)
        metric.child_collector({"B": "second"}).set(2)
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla{A="a",B="first"} 1.0' in metric_output
        assert 'logprep_bla{A="a",B="second"} 2.0' in metric_output
        assert 'logprep_bla{A="a",B=""} 0.0' in metric_output

    def test_child_collector_without_label_injection_registers_on_first_use(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"A": "a", "B": ""},
            registry=self.custom_registry,
        )
        metric.init_collector()
        child = metric.child_collector({"B": "b"}, inject_label_values=False)
        assert child.initialized
        assert 'B="b"' not in generate_latest(self.custom_registry).decode("utf-8")
        child.set(1)
        assert 'logprep_bla{A="a",B="b"} 1.0' in generate_latest(self.custom_registry).decode(
            "utf-8"
        )

    def test_child_collector_of_child_collector_keeps_merging_labels(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"A": "a", "B": "", "C": ""},
            registry=self.custom_registry,
        )
        metric.init_collector()
        grandchild = metric.child_collector({"B": "b"}).child_collector({"C": "c"})
        grandchild.set(1)
        assert 'logprep_bla{A="a",B="b",C="c"} 1.0' in generate_latest(self.custom_registry).decode(
            "utf-8"
        )

    def test_add_with_labels_none_value_raises_typeerror(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        with pytest.raises(TypeError, match="not supported between instances of 'NoneType'"):
            metric.add_with_labels(None, {"A": "a"})

    def test_add_with_labels_none_labels_raises_typeerror(self):
        metric = CounterMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        with pytest.raises(TypeError, match=" unsupported operand type(s) for |"):
            metric.add_with_labels(1, None)


class TestGaugeMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_collector_returns_collector(self):
        metric = GaugeMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert isinstance(metric._collector, Gauge)

    def test_gauge_metric_increments_correctly(self):
        metric = GaugeMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_collector()
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
        metric.init_collector()
        metric += 1
        metric += 1
        metric_output = generate_latest(self.custom_registry).decode("utf-8")
        assert 'logprep_bla{pipeline="1"} 1.0' in metric_output


class TestHistogramMetric:
    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def test_init_collector_returns_collector(self):
        metric = HistogramMetric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
            registry=self.custom_registry,
        )
        metric.init_collector()
        assert isinstance(metric._collector, Histogram)

    def test_gauge_metric_increments_correctly(self):
        metric = HistogramMetric(
            name="bla",
            description="empty description",
            labels={"pipeline": "1"},
            registry=self.custom_registry,
        )
        metric.init_collector()
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
        metric.init_collector()
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
        assert self.metrics.test_metric_number_1._collector is not None
        assert isinstance(self.metrics.test_metric_number_1._collector, Counter)

    def test_label_values_injection(self):
        assert self.metrics.test_metric_number_1._collector._labelnames == (
            "component",
            "name",
            "type",
            "description",
        )
        metrics_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert (
            "logprep_test_metric_number_1_total{"
            'component="test",description="test_description",name="test",type="test_type"'
            "} 0.0" in metrics_output
        )
        assert '"None"' not in metrics_output, "default labels should not be present"

    def test_no_label_values_injection(self):
        assert self.metrics.test_metric_without_label_values._collector._labelnames == (
            "component",
            "name",
            "type",
            "description",
        )
        metrics_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert "test_metric_without_label_values" not in metrics_output

    @mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"})
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

    @mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"})
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
    @mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"})
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
        with mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}):

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
            assert not document
            mock_perf_counter.assert_called()

    async def test_measure_time_measures_async_function(self):
        @Metric.measure_time(metric_name="test_metric_histogram")
        async def decorated_function(self, document):
            await asyncio.sleep(0.001)

        await decorated_function(self, {"test": "event"})

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        # a sync wrapper would only have timed how long the coroutine took to create
        sum_sample = next(
            sample
            for sample in self.metrics.test_metric_histogram.collect_samples()
            if sample.name.endswith("_sum")
        )
        assert sum_sample.value > 0.001

    @mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"})
    async def test_measure_time_appends_to_event_from_async_function(self):
        @Metric.measure_time(metric_name="test_metric_histogram")
        async def decorated_function(self, document):
            pass

        document = {"test": "event"}
        await decorated_function(self, document)
        assert document.get("processing_times", {}).get("test_rule") > 0

    @pytest.mark.parametrize("append_to_event", ["", "1"])
    def test_measure_time_measures_when_decorated_function_raises(self, append_to_event):
        with mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": append_to_event}):

            @Metric.measure_time(metric_name="test_metric_histogram")
            def decorated_function(self, document):
                raise ValueError("the decorated function failed")

            document = {"test": "event"}
            with pytest.raises(ValueError, match="the decorated function failed"):
                decorated_function(self, document)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        assert "processing_times" not in document, "there is no result to attribute a time to"

    def test_measure_time_does_not_append_for_objects_that_are_neither_rule_nor_pipeline(self):
        with mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"}):

            @Metric.measure_time(metric_name="test_metric_histogram")
            def decorated_function(self, document):
                pass

            unrelated = mock.Mock(spec=["metrics"])
            unrelated.metrics = self.metrics
            document = {"test": "event"}
            decorated_function(unrelated, document)

        metric_output = generate_latest(self.metrics.custom_registry).decode("utf-8")
        assert re.search(r"test_metric_histogram_count.* 1\.0", metric_output)
        assert "processing_times" not in document

    @mock_env({"LOGPREP_APPEND_MEASUREMENT_TO_EVENT": "1"})
    def test_measure_time_appends_pipeline_times_for_objects_without_rule_type(self):
        @Metric.measure_time(metric_name="test_metric_histogram")
        def decorated_function(self, document):
            pass

        class Pipelineish:  # the pipeline has no rule_type
            metrics = self.metrics
            _logprep_config = object()

        document = {"test": "event"}
        decorated_function(Pipelineish(), document)

        processing_times = document.get("processing_times")
        assert set(processing_times) == {"pipeline", "hostname"}
        assert processing_times.get("pipeline") > 0
