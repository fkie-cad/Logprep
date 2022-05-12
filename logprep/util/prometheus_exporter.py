"""This module contains functionality to start a prometheus exporter and expose metrics with it"""
import os
import shutil
from os import listdir, path
from os.path import isfile

from prometheus_client import start_http_server, multiprocess, REGISTRY, Gauge


class PrometheusStatsExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    metric_prefix: str = "logprep_"
    multi_processing_dir = None

    def __init__(self, status_logger_config, application_logger, metrics):
        self._logger = application_logger
        self._configuration = status_logger_config
        self._port = 8000
        self._metric_ids = [self.get_metric_id_from_name(metric) for metric in metrics]

        self._prepare_multiprocessing()
        self._extract_port_from(self._configuration)
        self._set_up_metrics()

    def get_metric_id_from_name(self, metric_name):
        """Returns the prometheus metric id of a given metric name"""
        return f"{self.metric_prefix}{metric_name}"

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
            The Id of the process whose metrics should be removed
        """
        directory = self.multi_processing_dir
        metric_files = [file for file in listdir(directory) if isfile(path.join(directory, file))]
        removed_files = []
        for filename in metric_files:
            if str(pid) in filename:
                os.remove(os.path.join(self.multi_processing_dir, filename))
                removed_files.append(filename)
        self._logger.debug(f"Removed stale metric files: {removed_files}")

    def _extract_port_from(self, configuration):
        target_configs = configuration.get("targets", [])
        for config in target_configs:
            if "prometheus" in config:
                self._port = config.get("prometheus").get("port")

    def _set_up_metrics(self):
        """Sets up the metrics that the prometheus exporter should expose"""
        self.metrics = {
            metric_id: Gauge(
                metric_id,
                "Tracks the overall processing status",
                labelnames=["component"],
                registry=None,
            )
            for metric_id in self._metric_ids
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
