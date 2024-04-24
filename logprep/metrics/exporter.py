"""This module contains functionality to start a prometheus exporter and expose metrics with it"""

import logging
import os
import shutil
import threading
from logging import getLogger

import uvicorn
from prometheus_client import REGISTRY, make_asgi_app, multiprocess

from logprep.util import defaults
from logprep.util.configuration import MetricsConfig


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, configuration: MetricsConfig):
        self.is_running = False
        self._logger = getLogger("Prometheus Exporter")
        self._logger.debug("Initializing Prometheus Exporter")
        self.configuration = configuration
        self._port = configuration.port
        self._app = make_asgi_app(REGISTRY)

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

    def _init_log_config(self) -> dict:
        """Use for Uvicorn same log formatter like for Logprep"""
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
        return log_config

    def _override_runtime_logging(self):
        """Uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        http_server_name = self._logger.name
        for logger_name in ["uvicorn", "uvicorn.access"]:
            logging.getLogger(logger_name).removeHandler(logging.getLogger(logger_name).handlers[0])
            logging.getLogger(logger_name).addHandler(
                logging.getLogger("Logprep").parent.handlers[0]
            )
        logging.getLogger("uvicorn.access").name = http_server_name
        logging.getLogger("uvicorn.error").name = http_server_name

    def run(self):
        """Starts the default prometheus http endpoint"""
        self._prepare_multiprocessing()

        self.uvicorn_config = self.configuration.uvicorn_config
        log_config = self._init_log_config()
        self.compiled_config = uvicorn.Config(
            **self.uvicorn_config,
            port=self._port,
            app=self._app,
            log_level="info",
            log_config=log_config,
        )
        self.server = uvicorn.Server(self.compiled_config)
        self._override_runtime_logging()
        self.thread = threading.Thread(daemon=True, target=self.server.run)
        self.thread.start()
        while not self.server.started:
            continue

        self._logger.info(f"Prometheus Exporter started on port {self._port}")
        self.is_running = True
