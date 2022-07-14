# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=line-too-long
import logging
from ctypes import c_double
from multiprocessing import Manager, Lock, Value
from time import time
from unittest import mock

import pytest

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metric import MetricTargets
from logprep.metrics.metric_exposer import MetricExposer
from logprep.processor.base.rule import Rule
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
        self.metric_targets = MetricTargets(
            file_target=logger,
            prometheus_target=PrometheusStatsExporter(self.config, logger),
        )
        self.exposer = MetricExposer(self.config, self.metric_targets, self.shared_dict, Lock())

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

    @mock.patch("logprep.metrics.metric_exposer.MetricExposer._send_to_output")
    @mock.patch("logprep.metrics.metric_exposer.MetricExposer._clear_storage")
    @mock.patch("logprep.metrics.metric_exposer.MetricExposer._aggregate_metrics")
    def test_expose_aggregated_metrics(
        self, send_to_output_mock, clear_storage_mock, aggregate_metrics_mock
    ):
        for _ in range(len(self.exposer._shared_dict)):
            self.exposer._store_metrics({"metrics": "metrics"})
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

    @mock.patch("logprep.metrics.metric_exposer.MetricExposer._store_metrics")
    @mock.patch(
        "logprep.metrics.metric_exposer.MetricExposer._expose_aggregated_metrics_from_shared_dict"
    )
    def test_expose_calls_expose_aggregate_if_configured(
        self, store_metrics_mock, expose_aggregate_mock
    ):
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        mock_metrics = mock.MagicMock()
        self.exposer.expose(mock_metrics)
        store_metrics_mock.assert_called()
        expose_aggregate_mock.assert_called()

    @mock.patch("logprep.metrics.metric_exposer.MetricExposer._send_to_output")
    def test_expose_calls_send_to_output_if_no_aggregation_is_configured(self, send_to_output_mock):
        config = self.config.copy()
        config["aggregate_processes"] = False
        self.exposer = MetricExposer(config, self.metric_targets, self.shared_dict, Lock())
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        mock_metrics = mock.MagicMock()
        self.exposer.expose(mock_metrics)
        send_to_output_mock.assert_called()
        mock_metrics.expose.assert_called()

    def test_expose_resets_statistics_if_cumulative_config_is_false(self):
        config = self.config.copy()
        config["cumulative"] = False
        self.exposer = MetricExposer(config, self.metric_targets, self.shared_dict, Lock())
        self.exposer._timer = Value(c_double, time() - self.config["period"])
        metrics = Rule.RuleMetrics(labels={"type": "generic"})
        metrics._number_of_matches = 3
        metrics.update_mean_processing_time(3)
        self.exposer.expose(metrics)
        assert metrics._number_of_matches == 0
        assert metrics._mean_processing_time == 0
        assert metrics._mean_processing_time_sample_counter == 0

    @pytest.mark.parametrize(
        "key, expected_stripped_key",
        [
            (
                "logprep_metrics;label:value,pipeline:pipval,foo:bar,muh:bi",
                "logprep_metrics;label:value,foo:bar,muh:bi",
            ),
            (
                "logprep_metrics;label:value,pipeline:pipval-1",
                "logprep_metrics;label:value",
            ),
            (
                "logprep_metrics;pipeline:pipval-1",
                "logprep_metrics",
            ),
            (
                "logprep_metrics;pipeline:pipval-1,foo:bar",
                "logprep_metrics;foo:bar",
            ),
            (
                "logprep_metrics;foo:bar,bi:bo",
                "logprep_metrics;foo:bar,bi:bo",
            ),
            (
                "logprep_metrics",
                "logprep_metrics",
            ),
        ],
    )
    def test_strip_key_removes_given_label_name_from_metric_identifyer(
        self, key, expected_stripped_key
    ):
        stripped_key = self.exposer._strip_key(key)
        assert stripped_key == expected_stripped_key
