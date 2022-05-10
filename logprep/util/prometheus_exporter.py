"""This module contains functionality to start a prometheus exporter and expose metrics with it"""
import os
import shutil

from prometheus_client import start_http_server, multiprocess, REGISTRY, Gauge


class PrometheusStatsExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    metric_prefix = "logprep_"
    multi_processing_dir = ""

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
        self.multi_processing_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if self.multi_processing_dir:
            if os.path.isdir(self.multi_processing_dir):
                shutil.rmtree(self.multi_processing_dir)
            if os.path.isfile(self.multi_processing_dir):
                raise ValueError(
                    "Environment variable 'PROMETHEUS_MULTIPROC_DIR' is a file and not a directory"
                )
            os.makedirs(self.multi_processing_dir, exist_ok=True)
            multiprocess.MultiProcessCollector(REGISTRY, self.multi_processing_dir)

    def remove_metrics_from_process(self, pid):
        """
        Remove the prometheus multiprocessing database file from the multiprocessing directory.
        This ensures that prometheus won't export stale metrics in case a process has died.

        Parameters
        ----------
        pid : int
            The Id of the process who's metrics should be removed
        """
        metric_data_files = [
            f
            for f in os.listdir(self.multi_processing_dir)
            if os.path.isfile(os.path.join(self.multi_processing_dir, f))
        ]
        removed_files = []
        for file in metric_data_files:
            if str(pid) in file:
                os.remove(os.path.join(self.multi_processing_dir, file))
                removed_files.append(file)
        self._logger.debug(f"Removed stale metric files: {removed_files}")

    def _extract_port_from(self, configuration):
        target_configs = configuration.get("targets", [])
        for config in target_configs:
            if "prometheus" in config:
                self._port = config.get("prometheus").get("port")

    def _set_up_metrics(self):
        """Sets up the metrics that the prometheus exporter should expose"""
        metric_ids = [
            f"{self.metric_prefix}processed",
            f"{self.metric_prefix}errors",
            f"{self.metric_prefix}warnings",
            f"{self.metric_prefix}matches",
            f"{self.metric_prefix}avg_processing_time",
        ]

        self.metrics = {
            metric_id: Gauge(
                metric_id,
                "Tracks the overall processing status",
                labelnames=["component"],
                registry=None,
            )
            for metric_id in metric_ids
        }

        self.tracking_interval = Gauge(
            f"{self.metric_prefix}tracking_interval_in_seconds",
            "Tracking interval",
            labelnames=["component"],
            registry=None,
        )

    def run(self):
        """Starts the default prometheus http endpoint"""
        start_http_server(self._port)
        self._logger.info(f"Prometheus Exporter started on port {self._port}")
