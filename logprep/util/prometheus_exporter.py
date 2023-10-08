"""This module contains functionality to start a prometheus exporter and expose metrics with it"""
import os
import shutil
import tempfile
from os import listdir, path
from os.path import isfile

from prometheus_client import REGISTRY, Gauge, multiprocess, start_http_server


class PrometheusStatsExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    metric_prefix: str = "logprep_"
    multi_processing_dir: str = None

    def __init__(self, status_logger_config, application_logger):
        self._logger = application_logger
        self.configuration = status_logger_config
        self._port = status_logger_config.get("metrics", {}).get("port", 8000)

        self._prepare_multiprocessing()
        self._set_up_metrics()

    def _prepare_multiprocessing(self):
        """
        Sets up the proper metric registry for multiprocessing and handles the necessary
        temporary multiprocessing directory that the prometheus client expects.
        """
        if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            self.multi_processing_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        else:
            self.multi_processing_dir = f"{tempfile.gettempdir()}/logprep/prometheus_multiproc_dir"
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

    def _set_up_metrics(self):
        """Sets up the metrics that the prometheus exporter should expose"""
        self.metrics = {}
        self.tracking_interval = Gauge(
            f"{self.metric_prefix}tracking_interval_in_seconds",
            "Tracking interval",
            labelnames=["component", "logprep_version", "config_version"],
            registry=None,
        )

    def create_new_metric_exporter(self, metric_id, labelnames):
        """Creates a new gauge metric exporter and appends it to the already existing ones"""
        exporter = Gauge(
            metric_id,
            "Tracks the overall processing status",
            labelnames=labelnames,
            registry=None,
        )
        self.metrics[metric_id] = exporter

    def run(self):
        """Starts the default prometheus http endpoint"""
        start_http_server(self._port)
        self._logger.info(f"Prometheus Exporter started on port {self._port}")
