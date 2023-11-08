# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import logging
from unittest import mock

from prometheus_client import REGISTRY

from logprep.metrics.exporter import PrometheusExporter


@mock.patch(
    "logprep.metrics.exporter.PrometheusExporter._prepare_multiprocessing",
    new=lambda *args, **kwargs: None,
)
class TestPrometheusExporter:
    def setup_method(self):
        REGISTRY.__init__()
        self.metrics_config = {"metrics": {"enabled": True, "port": 80}}

    def test_correct_setup(self):
        exporter = PrometheusExporter(self.metrics_config.get("metrics"))
        assert exporter._port == self.metrics_config["metrics"]["port"]

    def test_default_port_if_missing_in_config(self):
        metrics_config = {
            "metrics": {
                "period": 10,
                "enabled": True,
            }
        }
        exporter = PrometheusExporter(metrics_config)

        assert exporter._port == 8000

    @mock.patch("logprep.metrics.exporter.start_http_server")
    def test_run_starts_http_server(self, mock_http_server, caplog):
        with caplog.at_level(logging.INFO):
            exporter = PrometheusExporter(self.metrics_config)
            exporter.run()

        mock_http_server.assert_has_calls([mock.call(exporter._port)])
        assert f"Prometheus Exporter started on port {exporter._port}" in caplog.text
