# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import logging
import os
from logging import getLogger
from unittest import mock

import pytest
from prometheus_client import REGISTRY, Gauge

from logprep.util.prometheus_exporter import PrometheusStatsExporter


@mock.patch(
    "logprep.util.prometheus_exporter.PrometheusStatsExporter._prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestPrometheusStatsExporter:
    def setup_method(self, tmpdir):
        REGISTRY.__init__()
        self.metrics_config = {
            "metrics": {"period": 10, "enabled": True, "cumulative": True, "port": 80}
        }

    def test_correct_setup(self):
        exporter = PrometheusStatsExporter(
            self.metrics_config.get("metrics"), getLogger("test-logger")
        )
        assert not exporter.metrics
        assert isinstance(exporter.tracking_interval, Gauge)
        assert exporter._port == self.metrics_config["metrics"]["port"]

    def test_default_port_if_missing_in_config(self):
        metrics_config = {
            "metrics": {
                "period": 10,
                "enabled": True,
                "cumulative": True,
            }
        }
        exporter = PrometheusStatsExporter(metrics_config, getLogger("test-logger"))

        assert exporter._port == 8000

    @mock.patch("logprep.util.prometheus_exporter.start_http_server")
    def test_run_starts_http_server(self, mock_http_server, caplog):
        with caplog.at_level(logging.INFO):
            exporter = PrometheusStatsExporter(self.metrics_config, getLogger("test-logger"))
            exporter.run()

        mock_http_server.assert_has_calls([mock.call(exporter._port)])
        assert f"Prometheus Exporter started on port {exporter._port}" in caplog.text
