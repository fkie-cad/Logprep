# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
from unittest import mock

from prometheus_client import Gauge

from logprep.abc import Processor
from logprep.framework.metric_targets import (
    PrometheusMetricTarget,
    MetricFileTarget,
    split_key_label_string,
)
from logprep.framework.pipeline import Pipeline
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.rule import Rule
from logprep.util.prometheus_exporter import PrometheusStatsExporter


def test_split_key_label_string():
    key_label_string = "logprep_metric_name;label_one:1,label_two:2"
    key, labels = split_key_label_string(key_label_string)
    expected_key = "logprep_metric_name"
    expected_labels = {"label_one": "1", "label_two": "2"}
    assert expected_key == key
    assert expected_labels == labels


class TestMetricFileTarget:
    def setup_method(self):
        config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "aggregate_processes": True,
            "targets": [
                {"prometheus": {"port": 8000}},
            ],
        }
        logger = logging.getLogger("test-file-metric-logger")
        self.target = MetricFileTarget(logger)

    def test_convert_metrics_to_pretty_json(self):

        rule_metrics_one = Rule.RuleMetrics(labels={})
        specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={
                "pipeline": "pipeline-01",
                "processor": "generic_adder",
                "tree_type": "specific_tree_rules",
            },
            rules=[rule_metrics_one],
        )
        rule_metrics_two = Rule.RuleMetrics(labels={})
        generic_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={
                "pipeline": "pipeline-01",
                "processor": "generic_adder",
                "tree_type": "generic_tree_rules",
            },
            rules=[rule_metrics_two],
        )
        generic_adder_metrics = Processor.ProcessorMetrics(
            labels={"pipeline": "pipeline-01", "type": "processor", "processor": "generic_adder"},
            generic_rule_tree=generic_rule_tree_metrics,
            specific_rule_tree=specific_rule_tree_metrics,
        )

        rule_metrics_one = Rule.RuleMetrics(labels={})
        specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={
                "pipeline": "pipeline-01",
                "processor": "normalizer",
                "tree_type": "specific_tree_rules",
            },
            rules=[rule_metrics_one],
        )
        rule_metrics_two = Rule.RuleMetrics(labels={})
        generic_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={
                "pipeline": "pipeline-01",
                "processor": "normalizer",
                "tree_type": "generic_tree_rules",
            },
            rules=[rule_metrics_two],
        )
        normalizer_metrics = Processor.ProcessorMetrics(
            labels={"pipeline": "pipeline-01", "type": "processor", "processor": "normalizer"},
            generic_rule_tree=generic_rule_tree_metrics,
            specific_rule_tree=specific_rule_tree_metrics,
        )
        pipeline_metrics = Pipeline.PipelineMetrics(
            labels={"pipeline": "pipeline-01"}, pipeline=[generic_adder_metrics, normalizer_metrics]
        )

        exposed_metrics = pipeline_metrics.expose()
        json = self.target._convert_metrics_to_pretty_json(exposed_metrics)
        # TODO: Debug why there are actual RuleTreeMetrics Objects in the exposed information
        assert json == {}


class TestPrometheusMetricTarget:
    def setup_method(self):
        config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "aggregate_processes": True,
            "targets": [
                {"prometheus": {"port": 8000}},
            ],
        }
        logger = logging.getLogger("test-file-metric-logger")
        prometheus_exporter = PrometheusStatsExporter(config, logger)
        self.target = PrometheusMetricTarget(prometheus_exporter)

    def test_expose_creates_new_metric_exporter_if_it_does_not_exist_yet(self):
        metrics = Rule.RuleMetrics(labels={"type": "generic"})
        assert self.target._prometheus_exporter.metrics == {}
        exposed_metrics = metrics.expose()
        self.target.expose(exposed_metrics)
        assert len(self.target._prometheus_exporter.metrics) == len(exposed_metrics)
        for metric in self.target._prometheus_exporter.metrics.values():
            assert isinstance(metric, Gauge)

    @mock.patch("prometheus_client.Gauge.labels")
    def test_expose_calls_prometheus_exporter_with_expected_arguments(self, mock_labels):
        metrics = Rule.RuleMetrics(labels={"type": "generic", "foo": "2"})
        metrics.number_of_matches = 2
        metrics.update_mean_processing_time(3.2)
        self.target.expose(metrics.expose())
        mock_labels.assert_has_calls([mock.call(type="generic", foo="2"), mock.call().set(2)])
        mock_labels.assert_has_calls([mock.call(type="generic", foo="2"), mock.call().set(3.2)])
