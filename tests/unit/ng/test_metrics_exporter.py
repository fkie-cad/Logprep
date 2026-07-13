# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from unittest import mock

import pytest
from asgiref.testing import ApplicationCommunicator

from logprep.ng.metrics.exporter import PrometheusExporter, make_patched_asgi_app
from logprep.ng.util.configuration import MetricsConfig


class TestHealthEndpoint:
    def setup_method(self):
        self.scope = {
            "client": ("127.0.0.1", 32767),
            "headers": [],
            "http_version": "1.0",
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "scheme": "http",
            "server": ("127.0.0.1", 80),
            "type": "http",
        }
        self.communicator = None

    @pytest.fixture(autouse=True)
    async def teardown_communicator(self):
        yield
        if self.communicator:
            await self.communicator.wait()

    async def request_health(self, app):
        self.communicator = ApplicationCommunicator(app, self.scope)
        await self.communicator.send_input({"type": "http.request"})
        status = await self.communicator.receive_output(timeout=1)
        body = await self.communicator.receive_output(timeout=1)
        return status, body

    @pytest.mark.parametrize(
        ("functions", "expected_status", "expected_body"),
        [
            pytest.param([lambda: True], 200, b"OK", id="single-healthy"),
            pytest.param([lambda: True, lambda: True], 200, b"OK", id="all-healthy"),
            pytest.param([lambda: False], 503, b"FAIL", id="single-unhealthy"),
            pytest.param([lambda: True, lambda: False], 503, b"FAIL", id="one-unhealthy"),
        ],
    )
    async def test_health_endpoint_uses_provider_result(
        self, functions, expected_status, expected_body
    ):
        app = make_patched_asgi_app(lambda: functions)

        status, body = await self.request_health(app)

        assert status["status"] == expected_status
        assert expected_body in body["body"]

    async def test_health_endpoint_awaits_async_healthchecks(self):
        healthcheck = mock.AsyncMock(return_value=True)
        app = make_patched_asgi_app(lambda: [healthcheck])

        status, body = await self.request_health(app)

        assert status["status"] == 200
        assert b"OK" in body["body"]
        healthcheck.assert_awaited_once()

    async def test_health_endpoint_returns_fail_if_healthcheck_raises(self):
        healthcheck = mock.Mock(side_effect=RuntimeError("boom"))
        app = make_patched_asgi_app(lambda: [healthcheck])

        status, body = await self.request_health(app)

        assert status["status"] == 503
        assert b"FAIL" in body["body"]

    async def test_update_healthchecks_is_visible_to_existing_app(self):
        exporter = PrometheusExporter(MetricsConfig(enabled=True))
        exporter.app = make_patched_asgi_app(exporter._get_healthcheck_functions)
        old_healthcheck = mock.Mock(return_value=True)
        new_healthcheck = mock.Mock(return_value=False)

        exporter.update_healthchecks([old_healthcheck])
        status, _ = await self.request_health(exporter.app)
        assert status["status"] == 200

        exporter.update_healthchecks([new_healthcheck])
        status, body = await self.request_health(exporter.app)

        assert status["status"] == 503
        assert b"FAIL" in body["body"]
        old_healthcheck.assert_called_once()
        new_healthcheck.assert_called_once()


class TestPrometheusExporter:
    @mock.patch("logprep.ng.metrics.exporter.AsyncHTTPServer", autospec=True)
    async def test_run_serves_with_async_http_server(self, server_cls):
        exporter = PrometheusExporter(MetricsConfig(enabled=True, port=8000))

        await exporter.run()

        server_cls.return_value.run.assert_awaited_once_with()

    @mock.patch("logprep.ng.metrics.exporter.AsyncHTTPServer", autospec=True)
    async def test_wait_until_started_waits_for_async_http_server(self, server_cls):
        exporter = PrometheusExporter(MetricsConfig(enabled=True, port=8000))

        await exporter.wait_until_started()

        server_cls.return_value.wait_until_started.assert_awaited_once_with()

    @mock.patch("logprep.ng.metrics.exporter.AsyncHTTPServer", autospec=True)
    def test_stop_signals_async_http_server(self, server_cls):
        exporter = PrometheusExporter(MetricsConfig(enabled=True, port=8000))

        exporter.stop()

        server_cls.return_value.stop.assert_called_once_with()
