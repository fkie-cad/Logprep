# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=line-too-long
import asyncio
import os.path
from unittest import mock

import pytest
from asgiref.testing import ApplicationCommunicator
from prometheus_client import CollectorRegistry

from logprep.metrics.exporter import PrometheusExporter, make_patched_asgi_app
from logprep.util import http
from logprep.util.configuration import MetricsConfig


@mock.patch(
    "logprep.metrics.exporter.PrometheusExporter.prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestPrometheusExporter:
    def setup_method(self):
        self.metrics_config = MetricsConfig(enabled=True, port=8000)

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
        exporter.init_server()
        assert exporter.server.uvicorn_config.host == "0.0.0.0"

    def test_is_running_returns_false_when_server_not_set(self):
        exporter = PrometheusExporter(self.metrics_config)
        assert not exporter.is_running

    def test_is_running_returns_false_when_server_thread_not_set(self):
        exporter = PrometheusExporter(self.metrics_config)
        exporter.server = http.ThreadingHTTPServer({}, None, False)
        assert not exporter.is_running

    def test_is_running_returns_false_when_server_thread_is_not_alive(self):
        exporter = PrometheusExporter(self.metrics_config)
        exporter.server = http.ThreadingHTTPServer({}, None, False)
        exporter.server.thread = mock.Mock()
        exporter.server.thread.is_alive.return_value = False
        assert not exporter.is_running

    def test_is_running_returns_true_when_server_thread_is_alive(self):
        exporter = PrometheusExporter(self.metrics_config)
        exporter.server = http.ThreadingHTTPServer({}, None, False)
        exporter.server.thread = mock.Mock()
        exporter.server.thread.is_alive.return_value = True
        assert exporter.is_running


@mock.patch(
    "logprep.util.http.ThreadingHTTPServer", new=mock.create_autospec(http.ThreadingHTTPServer)
)
@mock.patch(
    "logprep.metrics.exporter.PrometheusExporter.prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestHealthEndpoint:
    """These tests uses the `asgiref.testing.ApplicationCommunicator` to test the ASGI app itself
    For more information see: https://dokk.org/documentation/django-channels/2.4.0/topics/testing/
    """

    def setup_method(self):
        self.metrics_config = MetricsConfig(enabled=True, port=8000)
        self.registry = CollectorRegistry()
        self.captured_status = None
        self.captured_headers = None
        # Setup ASGI scope
        self.scope = {
            "client": ("127.0.0.1", 32767),
            "headers": [],
            "http_version": "1.0",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "scheme": "http",
            "server": ("127.0.0.1", 80),
            "type": "http",
        }
        self.communicator = None

    def teardown_method(self):
        if self.communicator:
            asyncio.get_event_loop().run_until_complete(self.communicator.wait())

    def seed_app(self, app):
        self.communicator = ApplicationCommunicator(app, self.scope)

    @pytest.mark.parametrize(
        "functions, expected_status, expected_body",
        [
            ([lambda: True], 200, b"OK"),
            ([lambda: True, lambda: True], 200, b"OK"),
            ([lambda: False], 503, b"FAIL"),
            ([lambda: False, lambda: False], 503, b"FAIL"),
            ([lambda: False, lambda: True, lambda: True], 503, b"FAIL"),
        ],
    )
    @pytest.mark.asyncio
    async def test_asgi_app(self, functions, expected_status, expected_body):
        app = make_patched_asgi_app(functions)
        self.scope["path"] = "/health"
        self.seed_app(app)
        await self.communicator.send_input({"type": "http.request"})
        event = await self.communicator.receive_output(timeout=1)
        assert event["status"] == expected_status
        event = await self.communicator.receive_output(timeout=1)
        assert expected_body in event["body"]

    @pytest.mark.asyncio
    async def test_health_endpoint_calls_health_check_functions(self):
        exporter = PrometheusExporter(self.metrics_config)
        function_mock = mock.Mock(return_value=True)
        exporter.healthcheck_functions = [function_mock]
        exporter.run(daemon=False)
        self.scope["path"] = "/health"
        self.seed_app(exporter.app)
        await self.communicator.send_input({"type": "http.request"})
        event = await self.communicator.receive_output(timeout=1)
        assert event["status"] == 200
        event = await self.communicator.receive_output(timeout=1)
        assert b"OK" in event["body"]
        function_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_health_checks_injects_new_functions(self):
        exporter = PrometheusExporter(self.metrics_config)
        function_mock = mock.Mock(return_value=True)
        exporter.healthcheck_functions = [function_mock]
        exporter.run(daemon=False)
        exporter.server.thread = None
        self.scope["path"] = "/health"
        self.seed_app(exporter.app)
        await self.communicator.send_input({"type": "http.request"})
        event = await self.communicator.receive_output(timeout=1)
        assert event["status"] == 200
        event = await self.communicator.receive_output(timeout=1)
        assert b"OK" in event["body"]
        assert function_mock.call_count == 1, "initial function should be called"
        new_function_mock = mock.Mock(return_value=True)
        exporter.update_healthchecks([new_function_mock])
        self.scope["path"] = "/health"
        self.seed_app(exporter.app)
        await self.communicator.send_input({"type": "http.request"})
        event = await self.communicator.receive_output(timeout=1)
        assert event["status"] == 200
        event = await self.communicator.receive_output(timeout=1)
        assert b"OK" in event["body"]
        assert new_function_mock.call_count == 1, "New function should be called"
        assert function_mock.call_count == 1, "Old function should not be called"
