# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
import os
from logging import getLogger
from unittest import mock

import pytest
from prometheus_client import Gauge, REGISTRY

from logprep.util.prometheus_exporter import PrometheusStatsExporter


class TestPrometheusStatsExporter:
    def setup_method(self):
        REGISTRY.__init__()
        self.status_logger_config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "targets": [
                {"prometheus": {"port": 80}},
                {"file": {"path": "", "rollover_interval": 200, "backup_count": 10}},
            ],
        }

    def test_correct_setup(self):
        exporter = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))

        expected_metrics = {
            "logprep_processed",
            "logprep_errors",
            "logprep_warnings",
            "logprep_matches",
            "logprep_avg_processing_time",
        }

        created_metric_names = set(exporter.metrics.keys())

        missing_keys = expected_metrics.difference(created_metric_names)
        unknown_keys = created_metric_names.difference(expected_metrics)

        assert len(missing_keys) == 0, f"following metrics are missing: {missing_keys}"
        assert len(unknown_keys) == 0, f"following metrics are unexpected: {unknown_keys}"

        assert all(
            isinstance(exporter.metrics[metric_key], Gauge)
            for metric_key in exporter.metrics.keys()
        )

        assert isinstance(exporter.tracking_interval, Gauge)

        assert exporter._port == self.status_logger_config["targets"][0]["prometheus"]["port"]

    def test_default_port_if_missing_in_config(self):
        status_logger_config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "targets": [{"file": {"path": "", "rollover_interval": 200, "backup_count": 10}}],
        }
        exporter = PrometheusStatsExporter(status_logger_config, getLogger("test-logger"))

        assert exporter._port == 8000

    @mock.patch("logprep.util.prometheus_exporter.multiprocess")
    def test_prepare_multiprocessing_recreates_temp_directory_if_dir_exists_already(
        self, mock_multiprocess, tmp_path
    ):
        multi_proc_dir = tmp_path / "multi_proc_dir"
        os.makedirs(multi_proc_dir)
        test_file = os.path.join(multi_proc_dir, "dummy.txt")
        open(test_file, "w", encoding="utf-8").close()  # pylint: disable=consider-using-with

        with mock.patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": str(multi_proc_dir)}):
            _ = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))

        assert os.path.isdir(multi_proc_dir)
        assert not os.path.isfile(test_file)
        mock_multiprocess.assert_has_calls(
            [mock.call.MultiProcessCollector(REGISTRY, str(multi_proc_dir))]
        )

    @mock.patch("logprep.util.prometheus_exporter.multiprocess")
    def test_prepare_multiprocessing_creates_temp_dir_if_dir_does_not_exists(
        self, mock_multiprocess, tmp_path
    ):
        multi_proc_dir = tmp_path / "multi_proc_dir"
        assert not os.path.isdir(multi_proc_dir)

        with mock.patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": str(multi_proc_dir)}):
            _ = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))

        assert os.path.isdir(multi_proc_dir)
        mock_multiprocess.assert_has_calls(
            [mock.call.MultiProcessCollector(REGISTRY, str(multi_proc_dir))]
        )

    def test_prepare_multiprocessing_fails_if_env_variable_is_file(self, tmp_path):
        multi_proc_dir = tmp_path / "multi_proc_dir"
        os.makedirs(multi_proc_dir)
        test_file = os.path.join(multi_proc_dir, "dummy.txt")
        open(test_file, "w", encoding="utf-8").close()  # pylint: disable=consider-using-with

        with mock.patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": str(test_file)}):
            with pytest.raises(
                ValueError,
                match="Environment variable 'PROMETHEUS_MULTIPROC_DIR' "
                "is a file and not a directory",
            ):
                _ = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))

    @mock.patch("logprep.util.prometheus_exporter.multiprocess")
    @mock.patch("logprep.util.prometheus_exporter.os.makedirs")
    @mock.patch("logprep.util.prometheus_exporter.shutil.rmtree")
    def test_prepare_multiprocessing_does_not_init_prometheus_if_env_variable_is_missing(
        self, mock_multiprocess, mock_makedirs, mock_rmtree
    ):
        _ = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))

        mock_multiprocess.assert_not_called()
        mock_makedirs.assert_not_called()
        mock_rmtree.assert_not_called()

    @mock.patch("logprep.util.prometheus_exporter.start_http_server")
    def test_run_starts_http_server(self, mock_http_server, caplog):
        with caplog.at_level(logging.INFO):
            exporter = PrometheusStatsExporter(self.status_logger_config, getLogger("test-logger"))
            exporter.run()

        mock_http_server.assert_has_calls([mock.call(exporter._port)])
        assert f"Prometheus Exporter started on port {exporter._port}" in caplog.text

    def test_remove_metrics_from_process_removes_database_file_of_given_pid(self, tmp_path, caplog):
        # pylint: disable=consider-using-with
        multi_proc_dir = tmp_path / "multi_proc_dir"
        os.makedirs(multi_proc_dir)

        with mock.patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": str(multi_proc_dir)}):
            with caplog.at_level(logging.DEBUG):
                exporter = PrometheusStatsExporter(
                    self.status_logger_config, getLogger("test-logger")
                )
                metric_test_file_1 = os.path.join(multi_proc_dir, "gauge_5416.db")
                metric_test_file_2 = os.path.join(multi_proc_dir, "gauge_8742.db")
                open(metric_test_file_1, "a", encoding="utf-8").close()
                open(metric_test_file_2, "a", encoding="utf-8").close()

                exporter.remove_metrics_from_process(pid=5416)

            assert not os.path.isfile(metric_test_file_1)
            assert os.path.isfile(metric_test_file_2)
            assert "Removed stale metric files: ['gauge_5416.db']" in caplog.text
