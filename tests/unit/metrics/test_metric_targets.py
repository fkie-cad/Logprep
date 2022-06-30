# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import json
import logging
from datetime import datetime
from unittest import mock

import pytest
from prometheus_client import Gauge

from logprep.abc import Processor
from logprep.framework.pipeline import Pipeline
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric_targets import (
    PrometheusMetricTarget,
    MetricFileTarget,
    split_key_label_string,
)
from logprep.processor.base.rule import Rule
from logprep.util.prometheus_exporter import PrometheusStatsExporter


@pytest.fixture(name="pipeline_metrics")
def fixture_full_pipeline_metrics():
    rule_metrics_one = Rule.RuleMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "generic_adder",
            "rule_tree": "specific",
        }
    )
    specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "generic_adder",
            "rule_tree": "specific",
        },
        rules=[rule_metrics_one],
    )
    rule_metrics_two = Rule.RuleMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "generic_adder",
            "rule_tree": "generic",
        }
    )
    rule_metrics_two._number_of_matches = 2
    rule_metrics_three = Rule.RuleMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "generic_adder",
            "rule_tree": "generic",
        }
    )
    rule_metrics_three._number_of_matches = 3
    generic_rule_tree_metrics = RuleTree.RuleTreeMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "generic_adder",
            "rule_tree": "generic",
        },
        rules=[rule_metrics_two, rule_metrics_three],
    )
    generic_adder_metrics = Processor.ProcessorMetrics(
        labels={"pipeline": "pipeline-01", "processor": "generic_adder"},
        generic_rule_tree=generic_rule_tree_metrics,
        specific_rule_tree=specific_rule_tree_metrics,
    )

    rule_metrics_one = Rule.RuleMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "normalizer",
            "tree_type": "specific",
        }
    )
    specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "normalizer",
            "rule_tree": "specific",
        },
        rules=[rule_metrics_one],
    )
    rule_metrics_two = Rule.RuleMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "normalizer",
            "rule_tree": "generic",
        }
    )
    generic_rule_tree_metrics = RuleTree.RuleTreeMetrics(
        labels={
            "pipeline": "pipeline-01",
            "processor": "normalizer",
            "rule_tree": "generic",
        },
        rules=[rule_metrics_two],
    )
    normalizer_metrics = Processor.ProcessorMetrics(
        labels={"pipeline": "pipeline-01", "processor": "normalizer"},
        generic_rule_tree=generic_rule_tree_metrics,
        specific_rule_tree=specific_rule_tree_metrics,
    )
    pipeline_metrics = Pipeline.PipelineMetrics(
        labels={"pipeline": "pipeline-01"}, pipeline=[generic_adder_metrics, normalizer_metrics]
    )
    return pipeline_metrics


def test_split_key_label_string():
    key_label_string = "logprep_metric_name;label_one:1,label_two:2"
    key, labels = split_key_label_string(key_label_string)
    expected_key = "logprep_metric_name"
    expected_labels = {"label_one": "1", "label_two": "2"}
    assert expected_key == key
    assert expected_labels == labels


class TestMetricFileTarget:
    def setup_method(self):
        logger = logging.getLogger("test-file-metric-logger")
        self.target = MetricFileTarget(logger)

    def test_convert_metrics_to_pretty_json(self, pipeline_metrics):
        exposed_metrics = pipeline_metrics.expose()
        exposed_json = self.target._convert_metrics_to_pretty_json(exposed_metrics)
        expected_json = {
            "pipeline": {
                "pipeline-01": {
                    "processor": {
                        "generic_adder": {
                            "logprep_processor_number_of_processed_events": 0.0,
                            "logprep_processor_mean_processing_time_per_event": 0.0,
                            "logprep_processor_number_of_warnings": 0.0,
                            "logprep_processor_number_of_errors": 0.0,
                            "rule_tree": {
                                "generic": {
                                    "logprep_number_of_rules": 0.0,
                                    "logprep_number_of_matches": 5.0,
                                    "logprep_mean_processing_time": 0.0,
                                },
                                "specific": {
                                    "logprep_number_of_rules": 0.0,
                                    "logprep_number_of_matches": 0.0,
                                    "logprep_mean_processing_time": 0.0,
                                },
                            },
                        },
                        "normalizer": {
                            "logprep_processor_number_of_processed_events": 0.0,
                            "logprep_processor_mean_processing_time_per_event": 0.0,
                            "logprep_processor_number_of_warnings": 0.0,
                            "logprep_processor_number_of_errors": 0.0,
                            "rule_tree": {
                                "generic": {
                                    "logprep_number_of_rules": 0.0,
                                    "logprep_number_of_matches": 0.0,
                                    "logprep_mean_processing_time": 0.0,
                                },
                                "specific": {
                                    "logprep_number_of_rules": 0.0,
                                    "logprep_number_of_matches": 0.0,
                                    "logprep_mean_processing_time": 0.0,
                                },
                            },
                        },
                    },
                    "logprep_pipeline_kafka_offset": 0.0,
                    "logprep_pipeline_number_of_processed_events": 0.0,
                    "logprep_pipeline_number_of_warnings": 0.0,
                    "logprep_pipeline_number_of_errors": 0.0,
                }
            }
        }

        assert exposed_json == expected_json

    def test_add_timestamp_adds_meta_subfield_with_current_timestamp(self):
        metric_json = {"pipeline": "not important here"}
        metric_json = self.target._add_timestamp(metric_json)
        assert "meta" in metric_json
        assert "timestamp" in metric_json["meta"].keys()
        assert isinstance(
            datetime.strptime(metric_json["meta"]["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"), datetime
        )

    def test_expose_preprocesses_metrics_and_prints_them_to_the_logger(self, caplog):
        metrics = Rule.RuleMetrics(labels={"type": "generic"})
        exposed_metrics = metrics.expose()
        with caplog.at_level(logging.INFO):
            self.target.expose(exposed_metrics)
        assert len(caplog.messages) == 1
        exposed_json = json.loads(caplog.messages[0])
        assert isinstance(exposed_json, dict)
        assert "meta" in exposed_json
        assert "timestamp" in exposed_json["meta"]


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
        assert self.target.prometheus_exporter.metrics == {}
        exposed_metrics = metrics.expose()
        self.target.expose(exposed_metrics)
        assert len(self.target.prometheus_exporter.metrics) == len(exposed_metrics)
        for metric in self.target.prometheus_exporter.metrics.values():
            assert isinstance(metric, Gauge)

    @mock.patch("prometheus_client.Gauge.labels")
    def test_expose_calls_prometheus_exporter_with_expected_arguments(
        self, mock_labels, pipeline_metrics
    ):
        self.target.expose(pipeline_metrics.expose())
        mock_labels.assert_has_calls(
            [
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(5),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0),
            ]
        )
