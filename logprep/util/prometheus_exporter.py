"""This module contains functionality to start a prometheus exporter and expose metrics with it"""
import os
import shutil

from prometheus_client import start_http_server, multiprocess, REGISTRY, Info, Gauge


class PrometheusStatsExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, status_logger_config, application_logger):
        self._logger = application_logger
        self._configuration = status_logger_config
        self._port = 8000

        self._prepare_multiprocessing()
        self._extract_port_from(self._configuration)
        self._set_up_metrics()

    def _prepare_multiprocessing(self):
        """
        Sets up the proper metric registry for multiprocessing and handles the necessary
        temporary multiprocessing directory that the prometheus client expects.
        """
        multi_processing_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if multi_processing_dir:
            multiprocess.MultiProcessCollector(REGISTRY, multi_processing_dir)

            if os.path.isdir(multi_processing_dir):
                shutil.rmtree(multi_processing_dir)
            os.makedirs(multi_processing_dir, exist_ok=True)

    def _extract_port_from(self, configuration):
        target_configs = configuration.get("targets", [])
        for config in target_configs:
            if "prometheus" in config:
                self._port = config.get("prometheus").get("port")

    def _set_up_metrics(self):
        """Sets up the metrics that the prometheus exporter should expose"""
        metrics = [
            "processed",
            "errors",
            "warnings",
            "matches",
            "mean_matches_per_rule",
            "avg_processing_time",
        ]

        self.stats = {
            stat_key: Gauge(
                stat_key, "Tracks the overall processing status", labelnames=["of"], registry=None
            )
            for stat_key in metrics
        }

        self.info_metric = Info("tracking", "Gives general information about the tracking")
        self.info_metric.info({"interval_in_seconds": str(self._configuration.get("period"))})

    def run(self):
        """Starts the default prometheus http endpoint"""
        start_http_server(self._port)
        self._logger.info(f"Prometheus Exporter started on port {self._port}")
