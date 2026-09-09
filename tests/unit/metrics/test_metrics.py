# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import ast
import asyncio
import inspect
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
from prometheus_client.metrics import MetricWrapperBase

from logprep.abc.component import Component
from logprep.metrics import metrics as metrics_module
from logprep.metrics.metrics import CounterMetric, GaugeMetric, HistogramMetric, Metric
from tests.conftest import mock_env


@define(frozen=True, kw_only=True)
class MetricType:
    """Key aspects of a metric under test"""

    metric: type[Metric]
    collector: type[MetricWrapperBase]
    value_series_suffix: str
    collector_methods: set[str]

    @property
    def id(self) -> str:
        return self.metric.__name__.removesuffix("Metric").lower()


METRIC_TYPES = (
    MetricType(
        metric=CounterMetric,
        collector=Counter,
        value_series_suffix="_total",
        collector_methods={"inc"},
    ),
    MetricType(
        metric=GaugeMetric,
        collector=Gauge,
        value_series_suffix="",
        collector_methods={"set", "inc", "dec"},
    ),
    MetricType(
        metric=HistogramMetric,
        collector=Histogram,
        value_series_suffix="_sum",
        collector_methods={"observe"},
    ),
)

TYPE_CASES = [pytest.param(metric_type, id=metric_type.id) for metric_type in METRIC_TYPES]

WRITE_CASES = [
    pytest.param(
        CounterMetric, "inc", 3, 'logprep_some_metric_name_total{A="a"} 3.0', id="counter_inc"
    ),
    pytest.param(GaugeMetric, "set", 5, 'logprep_some_metric_name{A="a"} 5.0', id="gauge_set"),
    pytest.param(GaugeMetric, "inc", 2, 'logprep_some_metric_name{A="a"} 2.0', id="gauge_inc"),
    pytest.param(GaugeMetric, "dec", 2, 'logprep_some_metric_name{A="a"} -2.0', id="gauge_dec"),
    pytest.param(
        HistogramMetric, "observe", 0.5, 'logprep_some_metric_name_count{A="a"} 1.0', id="histogram"
    ),
]


ExampleMetric = CounterMetric
"""One concrete metric class to test base class functionality; could be any of the above"""


class MetricTestCase:
    """Gives every test its own registry, so values do not leak."""

    def setup_method(self):
        self.custom_registry = CollectorRegistry()

    def metric(self, metric_class, **kwargs):
        kwargs.setdefault("name", "some_metric_name")
        kwargs.setdefault("description", "empty description")
        kwargs.setdefault("labels", {"A": "a"})
        return metric_class(registry=self.custom_registry, **kwargs)

    def exposition(self) -> str:
        return generate_latest(self.custom_registry).decode("utf-8")

    @staticmethod
    def write(metric, method, argument):
        getattr(metric, method)(argument)


class TestMetric(MetricTestCase):

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_init_collector_creates_the_matching_collector(self, metric_type):
        metric = self.metric(metric_type.metric, name="testmetric")
        metric.init_collector()
        assert isinstance(metric._collector, metric_type.collector)

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_init_collector_does_not_raise_if_initialized_twice(self, metric_type):
        metric1 = self.metric(metric_type.metric, name="testmetric")
        metric2 = self.metric(metric_type.metric, name="testmetric")
        metric1.init_collector()
        metric2.init_collector()
        assert isinstance(metric1._collector, metric_type.collector)
        assert isinstance(metric2._collector, metric_type.collector)
        assert metric1._collector is metric2._collector

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_init_collector_reuses_collector_from_default_registry(self, metric_type):
        metric1 = metric_type.metric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
        )
        metric2 = metric_type.metric(
            name="testmetric",
            description="empty description",
            labels={"A": "a"},
        )
        metric1.init_collector()
        metric2.init_collector()

        assert metric1._collector is metric2._collector
        assert REGISTRY._names_to_collectors[metric1.fullname] is metric1._collector

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    @pytest.mark.parametrize(
        "labels",
        [pytest.param(None, id="no_labels"), pytest.param({}, id="empty_labels")],
    )
    def test_init_collector_raises_without_label_names(self, labels, metric_type):
        metric = metric_type.metric(
            name="some_metric_name",
            description="empty description",
            registry=self.custom_registry,
            **({} if labels is None else {"labels": labels}),
        )
        with pytest.raises(ValueError, match="No label names were set when constructing"):
            metric.init_collector()

    def test_init_collector_raises_on_try_to_overwrite_collector_with_different_type(self):
        counter = self.metric(CounterMetric, name="some_metric_name")
        counter.init_collector()
        histogram = self.metric(HistogramMetric, name="some_metric_name")
        with pytest.raises(ValueError, match="already exists with different type"):
            histogram.init_collector()

    @pytest.mark.parametrize(
        "registry_is_set",
        [pytest.param(True, id="with_registry"), pytest.param(False, id="without_registry")],
    )
    def test_init_collector_reraises_if_it_cannot_recover(self, registry_is_set):
        metric = self.metric(ExampleMetric)
        metric._registry = self.custom_registry if registry_is_set else None
        with mock.patch.object(
            metric, "_init_collector", side_effect=ValueError("unrelated failure")
        ):
            with pytest.raises(ValueError, match="unrelated failure"):
                metric.init_collector()
        assert not metric.initialized

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_initialized_is_true_only_after_init_collector(self, metric_type):
        metric = self.metric(metric_type.metric, name="testmetric")
        assert not metric.initialized
        metric.init_collector()
        assert metric.initialized

    @mock_env({"PROMETHEUS_MULTIPROC_DIR": "/tmp"})
    def test_registry_is_not_set_in_multiprocess_mode(self):
        metric = ExampleMetric(name="some_metric_name", description="empty")
        assert metric._registry is None

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_metric_sets_labels(self, metric_type):
        metric = self.metric(metric_type.metric, labels={"pipeline": "pipeline-1"})
        metric.init_collector()
        assert metric._collector._labelnames == ("pipeline",)

    @pytest.mark.parametrize(
        "metric_class, method, expected",
        [
            pytest.param(
                CounterMetric,
                "inc",
                'logprep_some_metric_name_total{pipeline="1"} 3.0',
                id="counter_sums",
            ),
            pytest.param(
                GaugeMetric,
                "set",
                'logprep_some_metric_name{pipeline="1"} 2.0',
                id="gauge_keeps_the_last",
            ),
            pytest.param(
                HistogramMetric,
                "observe",
                'logprep_some_metric_name_sum{pipeline="1"} 3.0',
                id="histogram_sums",
            ),
        ],
    )
    def test_two_metrics_with_the_same_labels_produce_the_same_metric(
        self, metric_class, method, expected
    ):
        metric1 = self.metric(metric_class, labels={"pipeline": "1"})
        metric2 = self.metric(metric_class, labels={"pipeline": "1"})
        metric1.init_collector()
        metric2.init_collector()
        assert metric1._collector._labelnames == metric2._collector._labelnames
        getattr(metric1, method)(1)
        getattr(metric2, method)(2)
        # exactly one series, so both metrics really wrote to the same child
        assert len(re.findall(re.escape(expected), self.exposition())) == 1

    @pytest.mark.parametrize(
        "metric_class, method, expected1, expected2",
        [
            pytest.param(
                CounterMetric,
                "inc",
                'logprep_some_metric_name_total{pipeline="1"} 1.0',
                'logprep_some_metric_name_total{pipeline="2"} 2.0',
                id="counter",
            ),
            pytest.param(
                GaugeMetric,
                "set",
                'logprep_some_metric_name{pipeline="1"} 1.0',
                'logprep_some_metric_name{pipeline="2"} 2.0',
                id="gauge",
            ),
            pytest.param(
                HistogramMetric,
                "observe",
                'logprep_some_metric_name_sum{pipeline="1"} 1.0',
                'logprep_some_metric_name_sum{pipeline="2"} 2.0',
                id="histogram",
            ),
        ],
    )
    def test_different_label_values_write_to_different_children(
        self, metric_class, method, expected1, expected2
    ):
        metric1 = self.metric(metric_class, labels={"pipeline": "1"})
        metric2 = self.metric(metric_class, labels={"pipeline": "2"})
        metric1.init_collector()
        metric2.init_collector()

        assert metric1._collector == metric2._collector
        getattr(metric1, method)(1)
        getattr(metric2, method)(2)
        metric_output = self.exposition()
        assert expected1 in metric_output
        assert expected2 in metric_output

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_collector_methods_are_bound_onto_the_instance(self, metric_type):
        expected_methods = metric_type.collector_methods
        metric = self.metric(metric_type.metric)
        assert metric_type.metric._collector_methods == expected_methods
        assert not expected_methods & metric.__dict__.keys()
        metric.init_collector()
        assert expected_methods <= metric.__dict__.keys()

    @pytest.mark.parametrize("metric_class, method, argument, expected", WRITE_CASES)
    def test_collector_methods_bind_and_write_on_first_call(
        self, metric_class, method, argument, expected
    ):
        metric = self.metric(metric_class, inject_label_values=False)
        metric.init_collector()
        assert method not in metric.__dict__
        assert 'A="a"' not in self.exposition()
        self.write(metric, method, argument)
        assert method in metric.__dict__
        assert expected in self.exposition()

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_every_collector_method_has_a_write_case(self, metric_type):
        covered = {case.values[1] for case in WRITE_CASES if case.values[0] is metric_type.metric}
        assert metric_type.collector_methods == covered

    def test_collector_methods_are_decorated_exactly_when_they_bind_lazily(self):
        # decorated with @_collector_method <-> calls _bind_default_child() in body
        module = ast.parse(inspect.getsource(metrics_module))
        for metric_type in METRIC_TYPES:
            class_node = next(
                node
                for node in module.body
                if isinstance(node, ast.ClassDef) and node.name == metric_type.metric.__name__
            )
            for method in class_node.body:
                if not isinstance(method, ast.FunctionDef):
                    continue
                decorated = any(
                    getattr(decorator, "id", None) == "_collector_method"
                    for decorator in method.decorator_list
                )
                binds_lazily = "_bind_default_child" in ast.dump(method)
                assert decorated == binds_lazily, (
                    f"{metric_type.metric.__name__}.{method.name}: "
                    f"decorated={decorated} but binds_lazily={binds_lazily}"
                )

    @pytest.mark.parametrize("metric_class, method, argument, expected", WRITE_CASES)
    def test_collector_methods_write_to_the_default_child(
        self, metric_class, method, argument, expected
    ):
        metric = self.metric(metric_class)
        metric.init_collector()
        self.write(metric, method, argument)
        assert expected in self.exposition()

    @pytest.mark.parametrize(
        "metric_class, method, writes, expected",
        [
            pytest.param(
                CounterMetric,
                "inc",
                (3, 1, 2),
                'logprep_some_metric_name_total{A="a"} 6.0',
                id="counter_sums",
            ),
            pytest.param(
                GaugeMetric,
                "set",
                (3, 1, 2),
                'logprep_some_metric_name{A="a"} 2.0',
                id="gauge_keeps_the_last",
            ),
            pytest.param(
                GaugeMetric,
                "inc",
                (3, 1, 2),
                'logprep_some_metric_name{A="a"} 6.0',
                id="gauge_sums",
            ),
            pytest.param(
                HistogramMetric,
                "observe",
                (3, 1, 2),
                'logprep_some_metric_name_sum{A="a"} 6.0',
                id="histogram_sums",
            ),
        ],
    )
    def test_repeated_writes_follow_the_semantics_of_the_metric_type(
        self, metric_class, method, writes, expected
    ):
        metric = self.metric(metric_class)
        metric.init_collector()
        for write in writes:
            getattr(metric, method)(write)
        assert expected in self.exposition()

    def test_histogram_exposes_sum_count_and_buckets(self):
        metric = self.metric(HistogramMetric)
        metric.init_collector()
        metric.observe(1)
        metric.observe(2)
        metric.observe(3)
        metric_output = self.exposition()
        assert re.search(r'logprep_some_metric_name_sum\{A="a"\} 6\.0', metric_output)
        assert re.search(r'logprep_some_metric_name_count\{A="a"\} 3\.0', metric_output)
        assert re.search(r'logprep_some_metric_name_bucket\{A="a",le=".*"\} \d+', metric_output)

    @pytest.mark.parametrize(
        "metric_class, method, argument, expected",
        [
            pytest.param(CounterMetric, "inc", 3, 3, id="counter"),
            pytest.param(GaugeMetric, "set", 5, 5, id="gauge_set"),
            pytest.param(GaugeMetric, "dec", 2, -2, id="gauge_dec"),
            pytest.param(HistogramMetric, "observe", 0.5, 0.5, id="histogram"),
        ],
    )
    def test_value_reads_the_series_of_the_metric_type(
        self, metric_class, method, argument, expected
    ):
        metric = self.metric(metric_class)
        metric.init_collector()
        assert metric.value == 0
        getattr(metric, method)(argument)
        assert metric.value == expected

    def test_value_sums_the_labeled_children(self):
        metric = self.metric(GaugeMetric, labels={"A": ""}, inject_label_values=False)
        metric.init_collector()
        metric.child_collector({"A": "first"}).set(1)
        metric.child_collector({"A": "second"}).set(2)
        assert metric.value == 3

    def test_histogram_value_is_the_sum_and_count_is_the_number_of_observations(self):
        metric = self.metric(HistogramMetric)
        metric.init_collector()
        metric.observe(0.5)
        metric.observe(1.5)
        assert metric.value == 2.0
        assert metric.count == 2

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_every_metric_type_declares_its_value_series(self, metric_type):
        # inherited from the base a new type would silently read the wrong series
        declared = metric_type.metric.__dict__["_value_series_suffix"]
        assert declared == metric_type.value_series_suffix

    def test_collect_samples_returns_labels_and_values(self):
        metric = self.metric(ExampleMetric)
        metric.init_collector()
        metric.inc(3)
        samples = [sample for sample in metric.collect_samples() if sample.name.endswith("_total")]
        assert [(sample.labels, sample.value) for sample in samples] == [({"A": "a"}, 3.0)]

    def test_collect_samples_returns_every_labeled_child(self):
        metric = self.metric(
            ExampleMetric,
            labels={"A": ""},
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

    @pytest.mark.parametrize("metric_type", TYPE_CASES)
    def test_collect_samples_on_uninitialized_metric_raises(self, metric_type):
        metric = self.metric(metric_type.metric)
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'collect'"):
            metric.collect_samples()

    def test_child_collector_returns_initialized_child(self):
        metric = self.metric(GaugeMetric, labels={"A": "a", "B": ""})
        metric.init_collector()
        child = metric.child_collector({"B": "b"})
        assert child.initialized
        assert child._collector is metric._collector
        assert child.labels == {"A": "a", "B": "b"}

    def test_child_collector_writes_to_its_own_labels(self):
        metric = self.metric(GaugeMetric, labels={"A": "a", "B": ""})
        metric.init_collector()
        metric.child_collector({"B": "first"}).set(1)
        metric.child_collector({"B": "second"}).set(2)
        metric_output = self.exposition()
        assert 'logprep_some_metric_name{A="a",B="first"} 1.0' in metric_output
        assert 'logprep_some_metric_name{A="a",B="second"} 2.0' in metric_output
        assert 'logprep_some_metric_name{A="a",B=""} 0.0' in metric_output

    def test_child_collector_without_label_injection_registers_on_first_use(self):
        metric = self.metric(GaugeMetric, labels={"A": "a", "B": ""})
        metric.init_collector()
        child = metric.child_collector({"B": "b"}, inject_label_values=False)
        assert child.initialized
        assert 'B="b"' not in self.exposition()
        child.set(1)
        assert 'logprep_some_metric_name{A="a",B="b"} 1.0' in self.exposition()

    def test_child_collector_of_child_collector_keeps_merging_labels(self):
        metric = self.metric(GaugeMetric, labels={"A": "a", "B": "", "C": ""})
        metric.init_collector()
        grandchild = metric.child_collector({"B": "b"}).child_collector({"C": "c"})
        grandchild.set(1)
        assert 'logprep_some_metric_name{A="a",B="b",C="c"} 1.0' in self.exposition()

    @pytest.mark.parametrize(
        "metric_class, expected",
        [
            pytest.param(
                CounterMetric, 'logprep_some_metric_name_total{A="first"} 2.0', id="counter"
            ),
            pytest.param(GaugeMetric, 'logprep_some_metric_name{A="first"} 2.0', id="gauge"),
            pytest.param(
                HistogramMetric, 'logprep_some_metric_name_count{A="first"} 1.0', id="histogram"
            ),
        ],
    )
    def test_add_with_labels_writes_to_the_given_labels(self, metric_class, expected):
        metric = self.metric(metric_class, labels={"A": ""}, inject_label_values=False)
        metric.init_collector()
        metric.add_with_labels(2, {"A": "first"})
        assert expected in self.exposition()

    def test_add_with_labels_none_value_raises_typeerror(self):
        metric = self.metric(ExampleMetric, name="testmetric")
        metric.init_collector()
        with pytest.raises(TypeError, match="not supported between instances of 'NoneType'"):
            metric.add_with_labels(None, {"A": "a"})

    def test_add_with_labels_none_labels_raises_typeerror(self):
        metric = self.metric(ExampleMetric, name="testmetric")
        metric.init_collector()
        with pytest.raises(TypeError, match=r"unsupported operand type\(s\)"):
            metric.add_with_labels(1, None)


class TestComponentMetrics:
    @define(kw_only=True)
    class Metrics(Component.Metrics):
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
