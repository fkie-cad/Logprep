# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
# pylint: disable=line-too-long
import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from unittest import mock
from unittest.mock import MagicMock

import pytest
from prometheus_client import Gauge

from logprep._version import get_versions
from logprep.abc import Processor
from logprep.abc.connector import Connector
from logprep.framework.pipeline import Pipeline
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric_exposer import MetricExposer
from logprep.metrics.metric_targets import (
    PrometheusMetricTarget,
    MetricFileTarget,
    split_key_label_string,
    get_metric_targets,
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

    input_metrics = Connector.ConnectorMetrics(
        labels={"pipeline": "pipeline-01", "connector": "input"}
    )
    output_metrics = Connector.ConnectorMetrics(
        labels={"pipeline": "pipeline-01", "connector": "output"}
    )

    pipeline_metrics = Pipeline.PipelineMetrics(
        input=input_metrics,
        output=output_metrics,
        labels={"pipeline": "pipeline-01"},
        pipeline=[generic_adder_metrics, normalizer_metrics],
    )
    return pipeline_metrics


def test_split_key_label_string():
    key_label_string = "logprep_metric_name;label_one:1,label_two:2"
    key, labels = split_key_label_string(key_label_string)
    expected_key = "logprep_metric_name"
    expected_labels = {"label_one": "1", "label_two": "2"}
    assert expected_key == key
    assert expected_labels == labels


class TestGetMetricTargets:
    def test_get_metric_targets_return_no_targets_with_empty_config(self):
        empty_config = {}
        targets = get_metric_targets(empty_config, logging.getLogger("test-logger"))
        assert targets.file_target is None
        assert targets.prometheus_target is None

    def test_get_metric_targets_returns_no_targets_if_disabled(self):
        empty_config = {"metrics": {"enabled": False}}
        targets = get_metric_targets(empty_config, logging.getLogger("test-logger"))
        assert targets.file_target is None
        assert targets.prometheus_target is None

    @mock.patch("logprep.metrics.metric_targets.MetricFileTarget.create")
    def test_get_metric_target_returns_only_file_target(self, create_file_target_mock):
        create_file_target_mock.return_value = mock.MagicMock()
        empty_config = {"metrics": {"enabled": True, "targets": [{"file": {"some": "thing"}}]}}
        targets = get_metric_targets(empty_config, logging.getLogger("test-logger"))
        assert isinstance(targets.file_target, MagicMock)
        assert targets.prometheus_target is None

    @mock.patch("logprep.metrics.metric_targets.PrometheusMetricTarget.create")
    def test_get_metric_target_returns_only_prometheus_target(self, create_prometheus_target_mock):
        create_prometheus_target_mock.return_value = mock.MagicMock()
        empty_config = {
            "metrics": {"enabled": True, "targets": [{"prometheus": {"some": "thing"}}]}
        }
        targets = get_metric_targets(empty_config, logging.getLogger("test-logger"))
        assert isinstance(targets.prometheus_target, MagicMock)
        assert targets.file_target is None

    @mock.patch("logprep.metrics.metric_targets.MetricFileTarget.create")
    @mock.patch("logprep.metrics.metric_targets.PrometheusMetricTarget.create")
    def test_get_metric_target_returns_both_targets(
        self, create_file_target_mock, create_prometheus_target_mock
    ):
        create_file_target_mock.return_value = mock.MagicMock()
        create_prometheus_target_mock.return_value = mock.MagicMock()
        empty_config = {
            "metrics": {
                "enabled": True,
                "targets": [{"prometheus": {"some": "thing"}}, {"file": {"some": "thing"}}],
            }
        }
        targets = get_metric_targets(empty_config, logging.getLogger("test-logger"))
        assert isinstance(targets.prometheus_target, MagicMock)
        assert isinstance(targets.file_target, MagicMock)


class TestMetricFileTarget:
    def setup_method(self):
        logger = logging.getLogger("test-file-metric-logger")
        self.logprep_config = {"version": 1, "other_fields": "are_unimportant_for_test"}
        self.target = MetricFileTarget(logger, self.logprep_config)

    def test_create_method(self):
        config = {"path": "./logs/status.json", "rollover_interval": 86400, "backup_count": 10}
        created_target = MetricFileTarget.create(config, {})
        assert isinstance(created_target._file_logger, logging.Logger)
        assert isinstance(created_target._file_logger.handlers[0], TimedRotatingFileHandler)
        assert created_target._file_logger.handlers[0].interval == config["rollover_interval"]
        assert created_target._file_logger.handlers[0].backupCount == config["backup_count"]
        assert created_target._file_logger.handlers[0].baseFilename.endswith(config["path"][1:])

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
                    "connector": {
                        "input": {
                            "logprep_connector_mean_processing_time_per_event": 0.0,
                            "logprep_connector_number_of_processed_events": 0.0,
                            "logprep_connector_number_of_warnings": 0.0,
                            "logprep_connector_number_of_errors": 0.0,
                        },
                        "output": {
                            "logprep_connector_mean_processing_time_per_event": 0.0,
                            "logprep_connector_number_of_processed_events": 0.0,
                            "logprep_connector_number_of_warnings": 0.0,
                            "logprep_connector_number_of_errors": 0.0,
                        },
                    },
                    "logprep_pipeline_kafka_offset": 0.0,
                    "logprep_pipeline_mean_processing_time_per_event": 0.0,
                    "logprep_pipeline_number_of_processed_events": 0.0,
                    "logprep_pipeline_number_of_warnings": 0.0,
                    "logprep_pipeline_number_of_errors": 0.0,
                }
            }
        }

        assert exposed_json == expected_json

    def test_convert_metrics_to_pretty_json_with_empty_labels(self):
        rule_metrics_one = Rule.RuleMetrics(labels={"foo": "bar"})
        specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={"foo": "bar"},
            rules=[rule_metrics_one],
        )
        exposed_metrics = specific_rule_tree_metrics.expose()
        stripped_metrics = dict(
            (MetricExposer._strip_key(key, label_name="foo"), value)
            for key, value in exposed_metrics.items()
        )
        exposed_json = self.target._convert_metrics_to_pretty_json(stripped_metrics)
        expected_json = {
            "logprep_number_of_rules": 0.0,
            "logprep_number_of_matches": 0.0,
            "logprep_mean_processing_time": 0.0,
        }

        assert exposed_json == expected_json

    def test_add_meta_information_adds_meta_subfield_with_timestamp_and_versions(self):
        metric_json = {"pipeline": "not important here"}
        metric_json = self.target._add_meta_information(metric_json)
        assert "meta" in metric_json
        assert "timestamp" in metric_json["meta"].keys()
        assert isinstance(
            datetime.strptime(metric_json["meta"]["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"), datetime
        )
        expected_versions = {
            "logprep": get_versions().get("version"),
            "config": self.logprep_config.get("version"),
        }
        assert metric_json["meta"]["version"] == expected_versions

    def test_add_meta_information_adds_unset_for_config_version_if_not_found(self):
        logger = logging.getLogger("test-file-metric-logger")
        logprep_config = {"config": "but without a version field"}
        target = MetricFileTarget(logger, logprep_config)

        metric_json = {"pipeline": "not important here"}
        metric_json = target._add_meta_information(metric_json)
        expected_versions = {
            "logprep": get_versions().get("version"),
            "config": "unset",
        }
        assert metric_json["meta"]["version"] == expected_versions

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
        self.logprep_config = {
            "version": 1,
            "metrics": {
                "period": 10,
                "enabled": True,
                "cumulative": True,
                "aggregate_processes": True,
                "targets": [
                    {"prometheus": {"port": 8000}},
                ],
            },
        }
        logger = logging.getLogger("test-file-metric-logger")
        prometheus_exporter = PrometheusStatsExporter(self.logprep_config.get("metrics"), logger)
        self.target = PrometheusMetricTarget(prometheus_exporter, self.logprep_config)

    def test_create_method(self, tmpdir):
        with mock.patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": f"{tmpdir}/some/dir"}):
            config = {"port": 8000}
            created_target = PrometheusMetricTarget.create(config, logging.getLogger("test-logger"))
            assert isinstance(created_target, PrometheusMetricTarget)
            assert isinstance(created_target.prometheus_exporter, PrometheusStatsExporter)
            assert not created_target.prometheus_exporter.metrics
            assert created_target.prometheus_exporter._port == config["port"]
            assert created_target.prometheus_exporter._logger.name == "test-logger"

    def test_create_method_without_env_variable(self, caplog):
        with caplog.at_level(logging.WARNING):
            with mock.patch.dict(os.environ, {}):
                config = {"port": 8000}
                created_target = PrometheusMetricTarget.create(
                    config, logging.getLogger("test-logger")
                )
                assert created_target is None
                assert (
                    caplog.messages[0] == "Prometheus Exporter was deactivated because "
                    "the mandatory environment variable 'PROMETHEUS_MULTIPROC_DIR' is missing."
                )

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
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(5.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="generic_adder", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="generic"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01", processor="normalizer", rule_tree="specific"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0.0),
                mock.call(pipeline="pipeline-01"),
                mock.call().set(0.0),
                mock.call(
                    component="logprep",
                    logprep_version=get_versions().get("version"),
                    config_version=self.logprep_config.get("version"),
                ),
                mock.call().set(self.logprep_config.get("metrics").get("period")),
            ]
        )

    @mock.patch("prometheus_client.Gauge.labels")
    def test_expose_calls_prometheus_exporter_and_sets_config_version_to_unset_if_no_config_version_found(
        self, mock_labels, pipeline_metrics
    ):
        logprep_config = {
            "metrics": {
                "period": 10,
                "enabled": True,
                "cumulative": True,
                "aggregate_processes": True,
                "targets": [
                    {"prometheus": {"port": 8000}},
                ],
            },
        }
        logger = logging.getLogger("test-file-metric-logger")
        prometheus_exporter = PrometheusStatsExporter(logprep_config.get("metrics"), logger)
        target = PrometheusMetricTarget(prometheus_exporter, logprep_config)
        target.expose(pipeline_metrics.expose())
        mock_labels.assert_has_calls(
            [
                mock.call(
                    component="logprep",
                    logprep_version=get_versions().get("version"),
                    config_version="unset",
                ),
                mock.call().set(logprep_config.get("metrics").get("period")),
            ]
        )

    @mock.patch("prometheus_client.Gauge.set")
    def test_expose_calls_prometheus_exporter_without_labels(self, mock_labels):
        rule_metrics_one = Rule.RuleMetrics(labels={"foo": "bar"})
        rule_metrics_one._number_of_matches = 3
        specific_rule_tree_metrics = RuleTree.RuleTreeMetrics(
            labels={"foo": "bar"},
            rules=[rule_metrics_one],
        )
        specific_rule_tree_metrics.number_of_rules = 3
        exposed_metrics = specific_rule_tree_metrics.expose()
        stripped_metrics = dict(
            (MetricExposer._strip_key(key, label_name="foo"), value)
            for key, value in exposed_metrics.items()
        )
        self.target.expose(stripped_metrics)
        mock_labels.assert_has_calls(
            [
                mock.call(3.0),
                mock.call(3.0),
                mock.call(0.0),
                mock.call(10),
            ]
        )
