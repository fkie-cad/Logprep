"""This module contains functionality to start a prometheus exporter and expose metrics with it"""

import os
import shutil
from logging import getLogger
from typing import Callable, Iterable

from prometheus_client import REGISTRY, make_asgi_app, multiprocess

from logprep.util import http
from logprep.util.configuration import MetricsConfig
from logprep.util.defaults import DEFAULT_HEALTH_STATE

logger = getLogger("Exporter")


def make_patched_asgi_app(functions: Iterable[Callable] | None) -> Callable:
    """Creates an ASGI app that includes health check and metrics handling"""

    prometheus_app = make_asgi_app(REGISTRY)

    functions = functions if functions else [lambda: DEFAULT_HEALTH_STATE]

    response_start_ok = {"type": "http.response.start", "status": 200}
    response_body_ok = {"type": "http.response.body", "body": b"OK"}
    response_start_fail = {"type": "http.response.start", "status": 503}
    response_body_fail = {"type": "http.response.body", "body": b"FAIL"}

    async def asgi_app(scope, receive, send):
        """asgi app with health check and metrics handling"""
        if scope["type"] == "http" and scope["path"] == "/health":
            success = all(f() for f in functions)
            await send(response_start_ok if success else response_start_fail)
            await send(response_body_ok if success else response_body_fail)
        else:
            await prometheus_app(scope, receive, send)

    return asgi_app


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    @property
    def is_running(self) -> bool:
        """Returns whether the exporter is running"""
        return self.server and self.server.thread and self.server.thread.is_alive()

    def __init__(self, configuration: MetricsConfig):
        logger.debug("Initializing Prometheus Exporter")
        self.configuration = configuration
        self.server = None
        self.healthcheck_functions = None
        self._multiprocessing_prepared = False
        self.app = None

    def prepare_multiprocessing(self):
        """
        Sets up the proper metric registry for multiprocessing and handles the necessary
        temporary multiprocessing directory that the prometheus client expects.
        """
        if self._multiprocessing_prepared:
            return
        multiprocess.MultiProcessCollector(REGISTRY)
        self._multiprocessing_prepared = True

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
        logger.info("Cleaned up %s", multiprocess_dir)

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

    def run(self, daemon=True):
        """Starts the default prometheus http endpoint"""
        if self.is_running:
            return
        port = self.configuration.port
        self.init_server(daemon=daemon)
        self.prepare_multiprocessing()
        self.server.start()
        logger.info("Prometheus Exporter started on port %s", port)

    def init_server(self, daemon=True) -> None:
        """Initializes the server"""
        if not self.app:
            self.app = make_patched_asgi_app(self.healthcheck_functions)
        port = self.configuration.port
        self.server = http.ThreadingHTTPServer(
            self.configuration.uvicorn_config | {"port": port, "host": "0.0.0.0"},
            self.app,
            daemon=daemon,
            logger_name="Exporter",
        )

    def restart(self):
        """Restarts the exporter"""
        if self.server and self.server.thread and self.server.thread.is_alive():
            self.server.shut_down()
        self.run()

    def update_healthchecks(self, healthcheck_functions: Iterable[Callable], daemon=True) -> None:
        """Updates the healthcheck functions"""
        self.healthcheck_functions = healthcheck_functions
        self.app = make_patched_asgi_app(self.healthcheck_functions)
        if self.server and self.server.thread and self.server.thread.is_alive():
            self.server.shut_down()
        self.init_server(daemon=daemon)
        self.run()
