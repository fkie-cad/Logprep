# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logging import getLogger

from prometheus_client import Gauge, Info, REGISTRY

from logprep.util.prometheus_exporter import PrometheusStatsExporter


class TestPrometheusStatsExporter:
    def setup_method(self):
        REGISTRY.__init__()

    def test_correct_setup(self):
        status_logger_config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "targets": [
                {"prometheus": {"port": 80}},
                {"file": {"path": "", "rollover_interval": 200, "backup_count": 10}},
            ],
        }
        exporter = PrometheusStatsExporter(status_logger_config, getLogger("test-logger"))

        expected_metrics = {
            "processed",
            "errors",
            "warnings",
            "matches",
            "mean_matches_per_rule",
            "avg_processing_time",
        }

        created_metric_names = set(exporter.stats.keys())

        missing_keys = expected_metrics.difference(created_metric_names)
        unknown_keys = created_metric_names.difference(expected_metrics)

        assert len(missing_keys) == 0, f"following metrics are missing: {missing_keys}"
        assert len(unknown_keys) == 0, f"following metrics are unexpected: {unknown_keys}"

        assert all(
            [isinstance(exporter.stats[metric_key], Gauge) for metric_key in exporter.stats.keys()]
        )

        assert isinstance(exporter.info_metric, Info)

        assert exporter._port == status_logger_config["targets"][0]["prometheus"]["port"]

        expected_label = {"interval_in_seconds": f"{status_logger_config['period']}"}
        tracked_tracking_interval = REGISTRY.get_sample_value("tracking_info", expected_label)
        assert tracked_tracking_interval == 1

    def test_default_port_if_missing_in_config(self):
        status_logger_config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "targets": [{"file": {"path": "", "rollover_interval": 200, "backup_count": 10}}],
        }
        exporter = PrometheusStatsExporter(status_logger_config, getLogger("test-logger"))

        assert exporter._port == 8000
