"""This module contains functionality to start a prometheus exporter and expose metrics with it"""

import os
import shutil
from logging import getLogger

from prometheus_client import REGISTRY, make_asgi_app, multiprocess

from logprep.util import http
from logprep.util.configuration import MetricsConfig


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, configuration: MetricsConfig):
        self.is_running = False
        logger_name = "Exporter"
        self._logger = getLogger(logger_name)
        self._logger.debug("Initializing Prometheus Exporter")
        self.configuration = configuration
        self._port = configuration.port
        self._app = make_asgi_app(REGISTRY)
        self._server = http.ThreadingHTTPServer(
            configuration.uvicorn_config | {"port": self._port, "host": "0.0.0.0"},
            self._app,
            daemon=True,
            logger_name=logger_name,
        )

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
        self._logger.info("Cleaned up %s", multiprocess_dir)

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
        self._server.start()
        self._logger.info("Prometheus Exporter started on port %s", self._port)
        self.is_running = True
