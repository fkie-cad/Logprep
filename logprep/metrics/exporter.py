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

    async def asgi_app(scope, receive, send):
        """asgi app with health check and metrics handling"""
        if scope["type"] == "http" and scope["path"] == "/health":
            await send(
                {
                    "type": "http.response.start",
                    "status": 200 if all(f() for f in functions) else 503,
                }
            )
            await send({"type": "http.response.body", "body": b"OK"})
        else:
            await prometheus_app(scope, receive, send)

    return asgi_app


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, configuration: MetricsConfig):
        self.is_running = False
        logger.debug("Initializing Prometheus Exporter")
        self.configuration = configuration
        self.healthcheck_functions = None
        self._server = None

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

    def run(self):
        """Starts the default prometheus http endpoint"""
        port = self.configuration.port
        self._init_server()
        self._prepare_multiprocessing()
        self._server.start()
        logger.info("Prometheus Exporter started on port %s", port)
        self.is_running = True

    def _init_server(self) -> None:
        """Initializes the server"""
        port = self.configuration.port
        self._server = http.ThreadingHTTPServer(
            self.configuration.uvicorn_config | {"port": port, "host": "0.0.0.0"},
            make_patched_asgi_app(self.healthcheck_functions),
            daemon=True,
            logger_name="Exporter",
        )
