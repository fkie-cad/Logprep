"""This module contains functionality to start a prometheus exporter and expose metrics with it"""

import asyncio
import typing
from logging import getLogger
from typing import Awaitable, Callable, Iterable

from prometheus_client import REGISTRY, make_asgi_app

from logprep.ng.util.configuration import MetricsConfig
from logprep.ng.util.defaults import DEFAULT_HEALTH_STATE
from logprep.ng.util.http import AsyncHTTPServer

logger = getLogger("Exporter")

Healthcheck = Callable[[], bool | Callable[[], Awaitable[bool]]]
HealthcheckProvider = Callable[[], Iterable[Healthcheck] | None]


async def _check(fn: Healthcheck) -> bool:
    try:
        result = fn()
        if asyncio.iscoroutine(result):
            return await result
        else:
            assert not isinstance(result, Awaitable)
            assert isinstance(result, bool)

            return result
    except Exception:
        return False


def make_patched_asgi_app(functions_provider: HealthcheckProvider) -> Callable:
    """Creates an ASGI app that includes health check and metrics handling"""

    prometheus_app = make_asgi_app(REGISTRY)

    response_start_ok = {"type": "http.response.start", "status": 200}
    response_body_ok = {"type": "http.response.body", "body": b"OK"}
    response_start_fail = {"type": "http.response.start", "status": 503}
    response_body_fail = {"type": "http.response.body", "body": b"FAIL"}

    async def asgi_app(scope, receive, send):
        """asgi app with health check and metrics handling"""
        if scope["type"] == "http" and scope["path"] == "/health":
            functions = functions_provider() or typing.cast(
                Iterable[Healthcheck], [lambda: DEFAULT_HEALTH_STATE]
            )
            results = await asyncio.gather(*(_check(f) for f in functions))
            success = all(results)

            await send(response_start_ok if success else response_start_fail)
            await send(response_body_ok if success else response_body_fail)
        else:
            await prometheus_app(scope, receive, send)

    return asgi_app


class PrometheusExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    def __init__(self, configuration: MetricsConfig):
        logger.debug("Initializing Prometheus Exporter")
        self._configuration = configuration
        self._healthcheck_functions: Iterable[Callable] | None = None
        self._app = make_patched_asgi_app(self._get_healthcheck_functions)
        port = self._configuration.port
        self._server = AsyncHTTPServer(
            self._configuration.uvicorn_config | {"port": port, "host": "0.0.0.0"},
            self._app,
        )

    async def run(self) -> None:
        """Starts the default prometheus http endpoint"""
        await self._server.run()

    async def wait_until_started(self) -> None:
        await self._server.wait_until_started()
        logger.info("Prometheus Exporter started on port %s", self._configuration.port)

    def _get_healthcheck_functions(self) -> Iterable[Healthcheck] | None:
        return self.healthcheck_functions

    def stop(self) -> None:
        """Shuts down the exporter"""
        self._server.stop()

    def update_healthchecks(
        self,
        healthcheck_functions: Iterable[Healthcheck],
    ) -> None:
        """Updates the healthcheck functions"""
        self.healthcheck_functions = tuple(healthcheck_functions)
