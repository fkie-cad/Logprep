# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
from ctypes import c_double
from multiprocessing import Manager, Lock, Value
from time import time
from unittest import mock

from logprep.framework.metric_exposer import MetricExposer
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.rule import Rule
from logprep.util.processor_stats import StatusLoggerCollection
from logprep.util.prometheus_exporter import PrometheusStatsExporter


class TestMetricExposer:
    def setup_method(self):
        self.config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "aggregate_processes": True,
            "targets": [
                {"prometheus": {"port": 8000}},
                {
                    "file": {
                        "path": "./logs/status.json",
                        "rollover_interval": 86400,
                        "backup_count": 10,
                    }
                },
            ],
        }

        self.shared_dict = Manager().dict()
        process_count = 4
        for idx in range(process_count):
            self.shared_dict[idx] = None

        logger = logging.getLogger("test-file-metric-logger")
        self.logger_collection = StatusLoggerCollection(
            file_logger=logger,
            prometheus_exporter=PrometheusStatsExporter(self.config, logger),
        )
        self.exposer = MetricExposer(self.config, self.logger_collection, self.shared_dict, Lock())

    def test_time_to_expose_returns_true_after_enough_time_has_passed(self):
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        assert self.exposer._time_to_expose()

    def test_time_to_expose_returns_false_if_not_enough_time_has_passed(self):
        self.exposer._timer = Value(c_double, time() + self.config["period"])
        assert not self.exposer._time_to_expose()

    def test_store_metrics_add_metrics_object_to_first_free_slot(self):
        storage_keys = self.exposer._shared_dict.keys()
        dummy_content = {"dummy": "content"}
        self.exposer._shared_dict[storage_keys[0]] = dummy_content
        rule_metrics = Rule.RuleMetrics(labels={"not": "needed"})
        self.exposer._store_metrics(rule_metrics)
        assert self.exposer._shared_dict[storage_keys[0]] == dummy_content
        assert self.exposer._shared_dict[storage_keys[1]] == rule_metrics
        assert self.exposer._shared_dict[storage_keys[2]] is None
        assert self.exposer._shared_dict[storage_keys[3]] is None

    def test_clear_storage_empties_shared_dict(self):
        storage_keys = self.exposer._shared_dict.keys()
        dummy_content = {"dummy": "content"}
        self.exposer._shared_dict[storage_keys[0]] = dummy_content
        self.exposer._clear_storage()
        assert all(value is None for value in self.exposer._shared_dict.values())

    @mock.patch("logprep.framework.metric_exposer.MetricExposer._send_to_output")
    @mock.patch("logprep.framework.metric_exposer.MetricExposer._clear_storage")
    @mock.patch("logprep.framework.metric_exposer.MetricExposer._aggregate_metrics")
    def test_expose_aggregated_metrics(
        self, send_to_output_mock, clear_storage_mock, aggregate_metrics_mock
    ):
        self.exposer._expose_aggregated_metrics_from_shared_dict()
        send_to_output_mock.assert_called()
        clear_storage_mock.assert_called()
        aggregate_metrics_mock.assert_called()

    def test_aggregate_metrics_combines_list_of_metrics_to_one(self):
        rule_metrics_one = Rule.RuleMetrics(labels={"type": "generic"})
        rule_metrics_one._number_of_matches = 1
        rule_metrics_one.update_mean_processing_time(1)
        rule_tree_one = RuleTree.RuleTreeMetrics(labels={"type": "tree"}, rules=[rule_metrics_one])
        rule_metrics_two = Rule.RuleMetrics(labels={"type": "generic"})
        rule_metrics_two._number_of_matches = 2
        rule_metrics_two.update_mean_processing_time(2)
        rule_tree_two = RuleTree.RuleTreeMetrics(labels={"type": "tree"}, rules=[rule_metrics_two])
        self.exposer._store_metrics(rule_tree_one)
        self.exposer._store_metrics(rule_tree_two)
        metrics = self.exposer._aggregate_metrics()
        expected_metrics = {
            "logprep_number_of_rules;type:tree": 0,
            "logprep_number_of_matches;type:tree": 3,
            "logprep_mean_processing_time;type:tree": 1.5,
        }

        assert metrics == expected_metrics

    def test_send_to_output_calls_expose_of_configured_targets(self):
        mock_file_target = mock.MagicMock()
        mock_prometheus_target = mock.MagicMock()
        self.exposer.output_targets = [mock_file_target, mock_prometheus_target]
        metrics = Rule.RuleMetrics(labels={"type": "generic"})
        self.exposer._send_to_output(metrics)
        self.exposer.output_targets[0].expose.assert_called_with(metrics)
        self.exposer.output_targets[1].expose.assert_called_with(metrics)

    @mock.patch("logprep.framework.metric_exposer.MetricExposer._store_metrics")
    @mock.patch(
        "logprep.framework.metric_exposer.MetricExposer._expose_aggregated_metrics_from_shared_dict"
    )
    def test_expose_calls_expose_aggregate_if_configured(
        self, store_metrics_mock, expose_aggregate_mock
    ):
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        mock_metrics = mock.MagicMock()
        self.exposer.expose(mock_metrics)
        store_metrics_mock.assert_called()
        expose_aggregate_mock.assert_called()

    @mock.patch("logprep.framework.metric_exposer.MetricExposer._store_metrics")
    @mock.patch("logprep.framework.metric_exposer.MetricExposer._send_to_output")
    def test_expose_calls_send_to_output_if_no_aggregation_is_configured(
        self, store_metrics_mock, send_to_output_mock
    ):
        config = self.config.copy()
        config["aggregate_processes"] = False
        self.exposer = MetricExposer(config, self.logger_collection, self.shared_dict, Lock())
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        mock_metrics = mock.MagicMock()
        self.exposer.expose(mock_metrics)
        store_metrics_mock.assert_called()
        send_to_output_mock.assert_called()
        mock_metrics.expose.assert_called()
