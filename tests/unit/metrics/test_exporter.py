# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=line-too-long
import logging
import os.path
from unittest import mock

from prometheus_client import REGISTRY

from logprep.metrics.exporter import PrometheusExporter
from logprep.util.configuration import MetricsConfig


@mock.patch(
    "logprep.metrics.exporter.PrometheusExporter._prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestPrometheusExporter:
    def setup_method(self):
        REGISTRY.__init__()
        self.metrics_config = MetricsConfig(enabled=True, port=80)

    def test_correct_setup(self):
        exporter = PrometheusExporter(self.metrics_config)
        assert exporter._port == self.metrics_config.port

    def test_default_port_if_missing_in_config(self):
        metrics_config = MetricsConfig(enabled=True)
        exporter = PrometheusExporter(metrics_config)
        assert exporter._port == 8000

    @mock.patch("logprep.metrics.exporter.start_http_server")
    def test_run_starts_http_server(self, mock_http_server, caplog):
        with caplog.at_level(logging.INFO):
            exporter = PrometheusExporter(self.metrics_config)
            exporter.run()

        mock_http_server.assert_has_calls([mock.call(exporter._port)])
        assert f"Prometheus Exporter started on port {exporter._port}" in caplog.text

    def test_cleanup_prometheus_multiprocess_dir_deletes_temp_dir_contents_but_not_the_dir_itself(
        self, tmp_path
    ):
        subdir = tmp_path / "foo"
        os.makedirs(subdir, exist_ok=True)
        test_file = subdir / "test.txt"
        test_file.touch()
        assert os.path.isfile(test_file)
        assert os.path.isdir(subdir)
        with mock.patch("os.environ", {"PROMETHEUS_MULTIPROC_DIR": tmp_path}):
            exporter = PrometheusExporter(self.metrics_config)
            exporter.cleanup_prometheus_multiprocess_dir()
        assert not os.path.isfile(test_file)
        assert not os.path.isdir(subdir)
        assert os.path.isdir(tmp_path)

    def test_cleanup_prometheus_multiprocess_dir_does_not_delete_temp_dir_if_env_is_not_set(
        self, tmp_path
    ):
        subdir = tmp_path / "foo"
        os.makedirs(subdir, exist_ok=True)
        test_file = subdir / "test.txt"
        test_file.touch()
        assert os.path.isfile(test_file)
        assert os.path.isdir(subdir)
        with mock.patch("os.environ", {"SOME_OTHER_ENV": tmp_path}):
            exporter = PrometheusExporter(self.metrics_config)
            exporter.cleanup_prometheus_multiprocess_dir()
        assert os.path.isfile(test_file)
        assert os.path.isdir(subdir)

    @mock.patch("logprep.metrics.exporter.multiprocess")
    def test_mark_process_dead_calls_multiprocess_mark_dead(self, mock_multiprocess):
        exporter = PrometheusExporter(self.metrics_config)
        test_process_id = 14
        exporter.mark_process_dead(test_process_id)
        mock_multiprocess.mark_process_dead.assert_called()
        mock_multiprocess.mark_process_dead.assert_called_with(test_process_id)
