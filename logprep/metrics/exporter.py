"""This module contains functionality to start a prometheus exporter and expose metrics with it"""

import os
import shutil
from logging import getLogger

from prometheus_client import REGISTRY, multiprocess, start_http_server

from logprep.util.configuration import MetricsConfig


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, status_logger_config: MetricsConfig):
        self.is_running = False
        self._logger = getLogger("Prometheus Exporter")
        self._logger.debug("Initializing Prometheus Exporter")
        self.configuration = status_logger_config
        self._port = status_logger_config.port

    def _prepare_multiprocessing(self):
        """
        Sets up the proper metric registry for multiprocessing and handles the necessary
        temporary multiprocessing directory that the prometheus client expects.
        """
        multiprocess.MultiProcessCollector(REGISTRY)

    def cleanup_prometheus_multiprocess_dir(self):
        """removes the prometheus multiprocessing directory"""
        multiprocess_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if not multiprocess_dir:
            return
        for root, dirs, files in os.walk(multiprocess_dir):
            for file in files:
                os.remove(os.path.join(root, file))
            for directory in dirs:
                shutil.rmtree(os.path.join(root, directory), ignore_errors=True)
        self._logger.info("Cleaned up %s" % multiprocess_dir)

    def mark_process_dead(self, pid):
        """
        Remove the prometheus multiprocessing database file from the multiprocessing directory.
        This ensures that prometheus won't export stale metrics in case a process has died.

        Parameters
        ----------
        pid : int
            The Id of the process whose metrics should be removed
        """
        multiprocess.mark_process_dead(pid)

    def run(self):
        """Starts the default prometheus http endpoint"""
        self._prepare_multiprocessing()
        start_http_server(self._port)
        self._logger.info(f"Prometheus Exporter started on port {self._port}")
        self.is_running = True
