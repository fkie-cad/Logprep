# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=line-too-long
import asyncio
import os.path
from unittest import mock

import pytest
import requests
from prometheus_client import REGISTRY

from logprep.metrics.exporter import PrometheusExporter, make_patched_asgi_app
from logprep.util import http
from logprep.util.configuration import MetricsConfig


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
        assert exporter.configuration.port == self.metrics_config.port

    def test_default_port_if_missing_in_config(self):
        metrics_config = MetricsConfig(enabled=True)
        exporter = PrometheusExporter(metrics_config)
        assert exporter.configuration.port == 8000

    @mock.patch("logprep.util.http.ThreadingHTTPServer.start")
    def test_run_starts_http_server(self, mock_http_server_start):
        exporter = PrometheusExporter(self.metrics_config)
        exporter.run()
        mock_http_server_start.assert_called()

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

    def test_exporter_spawns_server_on_all_interfaces(self):
        exporter = PrometheusExporter(self.metrics_config)
        exporter._init_server()
        assert exporter._server.server.config.host == "0.0.0.0"


@mock.patch(
    "logprep.metrics.exporter.PrometheusExporter._prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestHealthEndpoint:
    def setup_method(self):
        REGISTRY.__init__()
        self.metrics_config = MetricsConfig(enabled=True, port=80)

    def test_health_endpoint_returns_503_as_default_health_state(self):
        exporter = PrometheusExporter(self.metrics_config)
        exporter._server = http.ThreadingHTTPServer(
            exporter.configuration.uvicorn_config | {"port": 8000, "host": "0.0.0.0"},
            make_patched_asgi_app(exporter.healthcheck_functions),
            daemon=False,
            logger_name="Exporter",
        )
        exporter._server.start()
        resp = requests.get("http://localhost:8000/health", timeout=0.5)
        assert resp.status_code == 503
        exporter._server.shut_down()

    @pytest.mark.parametrize(
        "functions, expected",
        [
            ([lambda: True], 200),
            ([lambda: True, lambda: True], 200),
            ([lambda: False], 503),
            ([lambda: False, lambda: False], 503),
            ([lambda: False, lambda: True, lambda: True], 503),
        ],
    )
    def test_health_check_returns_status_code(self, functions, expected):
        exporter = PrometheusExporter(self.metrics_config)
        exporter._server = http.ThreadingHTTPServer(
            exporter.configuration.uvicorn_config | {"port": 8000, "host": "0.0.0.0"},
            make_patched_asgi_app(functions),
            daemon=False,
            logger_name="Exporter",
        )
        exporter._server.start()
        resp = requests.get("http://localhost:8000/health", timeout=0.5)
        assert resp.status_code == expected
        exporter._server.shut_down()
